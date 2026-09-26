import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .import_service import create_batch, parse_cnab, parse_ofx, parse_pdf, parse_xls
from .models import (
    BusinessProfileAssessment,
    FinancialTransaction,
    ImportBatch,
    ImportRow,
    ManagerialCategory,
)
from .profile_service import evaluate_maturity


def complete_profile(user):
    return BusinessProfileAssessment.objects.create(
        business=user.businesses.get(is_default=True),
        maturity_answers={'records': '1'},
        score=12,
        recommended_level=BusinessProfileAssessment.Level.MANAGERIAL,
        status=BusinessProfileAssessment.Status.COMPLETED,
        completed_at=timezone.now(),
    )


class AuthenticationAndOnboardingTests(TestCase):
    def test_signup_normalizes_email_and_redirects_to_onboarding(self):
        response = self.client.post(reverse('gastos:signup'), {
            'name': 'Ana Silva', 'email': 'ANA@EXAMPLE.COM',
            'password1': 'UmaSenha-Forte-2026', 'password2': 'UmaSenha-Forte-2026',
        })
        self.assertRedirects(response, reverse('gastos:onboarding_business'))
        self.assertTrue(User.objects.filter(username='ana@example.com', email='ana@example.com').exists())

    def test_duplicate_email_is_case_insensitive(self):
        User.objects.create_user(username='ana@example.com', email='ana@example.com', password='UmaSenha-Forte-2026')
        response = self.client.post(reverse('gastos:signup'), {
            'name': 'Outra Ana', 'email': 'ANA@example.com',
            'password1': 'OutraSenha-Forte-2026', 'password2': 'OutraSenha-Forte-2026',
        })
        self.assertContains(response, 'Já existe uma conta com esse e-mail.')
        self.assertEqual(User.objects.filter(email__iexact='ana@example.com').count(), 1)

    def test_external_next_is_rejected(self):
        user = User.objects.create_user(username='ana@example.com', email='ana@example.com', password='UmaSenha-Forte-2026')
        complete_profile(user)
        response = self.client.post(reverse('gastos:login'), {'email': user.email, 'password': 'UmaSenha-Forte-2026', 'next': 'https://evil.example/'})
        self.assertRedirects(response, reverse('gastos:dashboard'))

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get(reverse('gastos:logout')).status_code, 405)

    def test_user_without_assessment_cannot_open_dashboard(self):
        user = User.objects.create_user(username='ana@example.com', email='ana@example.com', password='UmaSenha-Forte-2026')
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse('gastos:dashboard')), reverse('gastos:onboarding_business'))

    def test_onboarding_is_resumable_and_preferences_do_not_change_level(self):
        user = User.objects.create_user(username='ana@example.com', email='ana@example.com', password='UmaSenha-Forte-2026')
        self.client.force_login(user)
        answers = {key: '1' for key in ('records', 'update_frequency', 'monthly_volume', 'future_commitments', 'people_involved', 'predictability', 'management_need', 'advanced_controls')}
        response = self.client.post(reverse('gastos:onboarding_profile'), answers)
        self.assertRedirects(response, reverse('gastos:onboarding_preferences'))
        assessment = user.businesses.get(is_default=True).profile_assessments.get(is_current=True)
        original_level = assessment.recommended_level
        self.client.post(reverse('gastos:onboarding_preferences'), {'language': 'technical', 'detail': 'detailed', 'focus': 'growth', 'frequency': 'weekly', 'alerts': 'immediate'})
        assessment.refresh_from_db()
        self.assertEqual(assessment.recommended_level, original_level)
        self.assertEqual(assessment.status, BusinessProfileAssessment.Status.COMPLETED)


class ProfileRulesTests(TestCase):
    def test_boundaries_and_missing_material_data(self):
        eight = {'records': '2', 'update_frequency': '2', **{key: '0' for key in ('monthly_volume', 'future_commitments', 'people_involved', 'predictability', 'management_need', 'advanced_controls')}}
        result = evaluate_maturity(eight)
        self.assertEqual(result['recommended_level'], 'essential')
        self.assertTrue(result['is_boundary'])
        unknown = {key: 'unknown' for key in eight}
        missing = evaluate_maturity(unknown)
        self.assertFalse(missing['definitive'])
        self.assertEqual(missing['recommended_level'], '')


class ParserContractTests(TestCase):
    def test_ofx_and_cnab_240_return_the_same_intermediate_contract(self):
        ofx = b'<OFX><STMTTRN><TRNAMT>-149.90<DTPOSTED>20260926<MEMO>Hospedagem<FITID>ABC123</STMTTRN></OFX>'
        ofx_row = parse_ofx(ofx)[0]
        header = list('0' * 240); header[0:3] = '001'; header[7] = '0'
        detail = list('0' * 240); detail[13] = 'T'; detail[37:57] = f'{"Cliente":<20}'; detail[62:73] = f'{"ABC123":<11}'; detail[73:81] = '26092026'; detail[81:96] = '000000000014990'
        trailer = list('0' * 240); trailer[0:3] = '001'; trailer[7] = '9'
        cnab_row = parse_cnab((''.join(header) + '\n' + ''.join(detail) + '\n' + ''.join(trailer)).encode())[0]
        for row in (ofx_row, cnab_row):
            self.assertEqual(row.date.isoformat(), '2026-09-26')
            self.assertGreater(row.amount, 0)
            self.assertFalse(row.errors)

    @patch('gastos.import_service.PdfReader')
    def test_text_pdf_is_parsed_and_scanned_pdf_is_rejected(self, reader_mock):
        reader_mock.return_value.is_encrypted = False
        reader_mock.return_value.pages = [type('Page', (), {'extract_text': lambda self: '26/09/2026 Hospedagem 149,90 saída'})()]
        self.assertEqual(parse_pdf(b'%PDF')[0].description, 'Hospedagem')
        reader_mock.return_value.pages = [type('Page', (), {'extract_text': lambda self: ''})()]
        with self.assertRaisesMessage(Exception, 'PDF sem camada textual'):
            parse_pdf(b'%PDF')

    @patch('gastos.import_service.xlrd.open_workbook')
    def test_xls_reads_values_from_first_sheet_only(self, open_workbook):
        values = [['data', 'descricao', 'valor', 'natureza'], ['26/09/2026', 'Hospedagem', 149.90, 'saida']]
        sheet = type('Sheet', (), {
            'nrows': 2, 'ncols': 4,
            'cell_value': lambda self, row, col: values[row][col],
            'cell_type': lambda self, row, col: 1,
        })()
        workbook = type('Workbook', (), {'sheet_by_index': lambda self, index: sheet, 'release_resources': lambda self: None})()
        open_workbook.return_value = workbook
        row = parse_xls(b'xls')[0]
        self.assertEqual(row.description, 'Hospedagem')
        self.assertFalse(row.errors)


class ImportFlowTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=Path(self.temp_dir.name))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.temp_dir.cleanup)
        self.user = User.objects.create_user(username='ana@example.com', email='ana@example.com', password='UmaSenha-Forte-2026')
        complete_profile(self.user)
        self.business = self.user.businesses.get(is_default=True)
        self.category = ManagerialCategory.objects.create(business=self.business, name='Operação')
        self.client.force_login(self.user)

    def upload(self, content=None, name='extrato.csv'):
        content = content or b'data;descricao;valor;natureza\n26/09/2026;Hospedagem;149,90;saida\n'
        with patch('gastos.import_service.classificar_descricoes', return_value=[]):
            return self.client.post(reverse('gastos:imports'), {'file': SimpleUploadedFile(name, content, content_type='text/csv')})

    def test_csv_preview_does_not_create_transaction_and_confirmation_is_idempotent(self):
        response = self.upload()
        batch = ImportBatch.objects.get()
        self.assertRedirects(response, reverse('gastos:import_review', args=[batch.public_id]))
        self.assertEqual(FinancialTransaction.objects.count(), 0)
        row = batch.rows.get()
        self.client.post(reverse('gastos:import_review', args=[batch.public_id]), {f'row_{row.id}_decision': 'include', f'row_{row.id}_category': self.category.id})
        self.client.post(reverse('gastos:import_confirm', args=[batch.public_id]))
        self.client.post(reverse('gastos:import_confirm', args=[batch.public_id]))
        self.assertEqual(FinancialTransaction.objects.filter(source=FinancialTransaction.Source.IMPORT).count(), 1)
        batch.refresh_from_db()
        self.assertFalse(bool(batch.stored_file))

    def test_duplicate_file_and_other_business_access_are_blocked(self):
        first = self.upload()
        self.assertEqual(first.status_code, 302)
        second = self.upload()
        self.assertContains(second, 'já foi enviado', status_code=200)
        other = User.objects.create_user(username='bia@example.com', email='bia@example.com', password='UmaSenha-Forte-2026')
        complete_profile(other)
        self.client.force_login(other)
        batch = ImportBatch.objects.get(business=self.business)
        self.assertEqual(self.client.get(reverse('gastos:import_review', args=[batch.public_id])).status_code, 404)

    def test_invalid_extension_empty_pdf_and_unknown_cnab_are_rejected(self):
        self.assertContains(self.upload(b'abc', 'extrato.exe'), 'Formato não aceito', status_code=200)
        self.assertContains(self.upload(b'%PDF-1.4\n%%EOF', 'extrato.pdf'), 'PDF inválido', status_code=200)
        cnab = ('000' + '0' * 237 + '\n' + '999' + '9' * 237).encode()
        self.assertContains(self.upload(cnab, 'retorno.cnab'), 'Banco CNAB não reconhecido', status_code=200)

    def test_expiration_removes_raw_file(self):
        uploaded = SimpleUploadedFile('extrato.csv', b'data;descricao;valor;natureza\n26/09/2026;Hospedagem;149,90;saida\n')
        with patch('gastos.import_service.classificar_descricoes', return_value=[]):
            batch = create_batch(business=self.business, user=self.user, uploaded_file=uploaded)
        ImportBatch.objects.filter(pk=batch.pk).update(created_at=timezone.now() - timedelta(hours=25))
        call_command('expire_imports')
        batch.refresh_from_db()
        self.assertEqual(batch.status, ImportBatch.Status.EXPIRED)
        self.assertFalse(bool(batch.stored_file))
