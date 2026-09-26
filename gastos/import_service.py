import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import xlrd
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from pypdf import PdfReader

from .ia import classificar_descricoes
from .models import FinancialTransaction, ImportBatch, ImportRow, ManagerialCategory


@dataclass
class ParsedRow:
    row_number: int
    date: object = None
    description: str = ''
    amount: Decimal = None
    direction: str = ''
    external_identifier: str = ''
    errors: list = field(default_factory=list)


def sanitize_filename(name):
    stem = re.sub(r'[^A-Za-z0-9._-]+', '_', Path(name).name).strip('._')
    return stem[:180] or 'arquivo'


def detect_format(filename):
    suffix = Path(filename).suffix.lower().lstrip('.')
    if suffix in {'ofx', 'ofc'}:
        return ImportBatch.Format.OFX
    if suffix in {'cnab', 'ret'}:
        return ImportBatch.Format.CNAB
    if suffix in {'csv', 'xls', 'pdf'}:
        return suffix
    raise ValidationError('Formato não aceito. Envie OFX/OFC, CSV, XLS, PDF ou CNAB.')


def parse_date(value):
    raw = str(value or '').strip()[:10]
    for pattern in ('%Y-%m-%d', '%d/%m/%Y', '%Y%m%d', '%d%m%Y', '%d%m%y'):
        try:
            return datetime.strptime(raw, pattern).date()
        except ValueError:
            continue
    return None


def parse_amount(value):
    raw = str(value or '').strip().replace('R$', '').replace(' ', '')
    if ',' in raw:
        raw = raw.replace('.', '').replace(',', '.')
    try:
        return Decimal(raw).quantize(Decimal('0.01'))
    except InvalidOperation:
        return None


def normalize_row(number, date, description, amount, direction='', external_identifier=''):
    parsed_amount = parse_amount(amount)
    normalized_direction = str(direction or '').strip().lower()
    if normalized_direction in {'entrada', 'credito', 'crédito', 'credit', 'c'}:
        normalized_direction = FinancialTransaction.Direction.INFLOW
    elif normalized_direction in {'saida', 'saída', 'debito', 'débito', 'debit', 'd'}:
        normalized_direction = FinancialTransaction.Direction.OUTFLOW
    elif parsed_amount is not None:
        normalized_direction = FinancialTransaction.Direction.INFLOW if parsed_amount >= 0 else FinancialTransaction.Direction.OUTFLOW
    errors = []
    parsed_date = parse_date(date)
    if not parsed_date:
        errors.append('Data inválida ou ausente.')
    if not str(description or '').strip():
        errors.append('Descrição ausente.')
    if parsed_amount is None or parsed_amount == 0:
        errors.append('Valor inválido ou igual a zero.')
    if normalized_direction not in dict(FinancialTransaction.Direction.choices):
        errors.append('Natureza inválida.')
    return ParsedRow(
        number,
        parsed_date,
        str(description or '').strip()[:240],
        abs(parsed_amount) if parsed_amount else None,
        normalized_direction,
        str(external_identifier or '').strip()[:160],
        errors,
    )


def decode_text(data):
    for encoding in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationError('Não foi possível identificar a codificação do arquivo.')


def parse_csv(data, options=None):
    text = decode_text(data)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t|')
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    options = options or {}
    aliases = {
        'date': {'data', 'date'}, 'description': {'descricao', 'descrição', 'historico', 'histórico', 'description'},
        'amount': {'valor', 'amount'}, 'direction': {'natureza', 'tipo', 'direction'},
    }
    mapping = {}
    for key, names in aliases.items():
        configured = str(options.get(f'{key}_column') or '').strip().lower()
        mapping[key] = next((header for header in (reader.fieldnames or []) if header.strip().lower() == configured), None) if configured else None
        mapping[key] = mapping[key] or next((header for header in (reader.fieldnames or []) if header.strip().lower() in names), None)
    if not all(mapping.values()):
        raise ValidationError('O CSV deve conter colunas de data, descrição, valor e natureza.')
    return [normalize_row(index, row[mapping['date']], row[mapping['description']], row[mapping['amount']], row[mapping['direction']]) for index, row in enumerate(reader, 2)]


def parse_xls(data, options=None):
    options = options or {}
    try:
        workbook = xlrd.open_workbook(file_contents=data, on_demand=True)
        sheet_name = str(options.get('sheet_name') or '').strip()
        sheet = workbook.sheet_by_name(sheet_name) if sheet_name else workbook.sheet_by_index(0)
    except (xlrd.XLRDError, IndexError) as exc:
        raise ValidationError('XLS inválido ou sem planilha legível.') from exc
    if sheet.nrows < 2:
        return []
    headers = [str(sheet.cell_value(0, col)).strip().lower() for col in range(sheet.ncols)]
    required = {'date': None, 'description': None, 'amount': None, 'direction': None}
    variants = {'description': {'descricao', 'descrição', 'historico', 'histórico'}, 'direction': {'natureza', 'tipo'}, 'date': {'data'}, 'amount': {'valor'}}
    for name, names in variants.items():
        configured = str(options.get(f'{name}_column') or '').strip().lower()
        required[name] = next((i for i, header in enumerate(headers) if header == configured), None) if configured else None
        required[name] = required[name] if required[name] is not None else next((i for i, header in enumerate(headers) if header in names), None)
    if any(value is None for value in required.values()):
        raise ValidationError('A primeira aba do XLS deve conter data, descrição, valor e natureza.')
    rows = []
    for number in range(1, sheet.nrows):
        date_value = sheet.cell_value(number, required['date'])
        if sheet.cell_type(number, required['date']) == xlrd.XL_CELL_DATE:
            date_value = datetime(*xlrd.xldate_as_tuple(date_value, workbook.datemode)[:3]).date().isoformat()
        rows.append(normalize_row(number + 1, date_value, sheet.cell_value(number, required['description']), sheet.cell_value(number, required['amount']), sheet.cell_value(number, required['direction'])))
    workbook.release_resources()
    return rows


def ofx_value(block, tag):
    match = re.search(rf'<{tag}>\s*([^<\r\n]+)', block, re.I)
    return match.group(1).strip() if match else ''


def parse_ofx(data):
    text = decode_text(data)
    blocks = re.findall(r'<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|$)', text, re.I | re.S)
    if not blocks:
        raise ValidationError('OFX/OFC sem movimentações reconhecíveis.')
    return [normalize_row(i, ofx_value(block, 'DTPOSTED')[:8], ofx_value(block, 'MEMO') or ofx_value(block, 'NAME'), ofx_value(block, 'TRNAMT'), '', ofx_value(block, 'FITID')) for i, block in enumerate(blocks, 1)]


def parse_pdf(data):
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValidationError('PDF criptografado não é aceito.')
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError('PDF inválido ou malformado.') from exc
    if not text.strip():
        raise ValidationError('PDF sem camada textual. OCR não está disponível nesta versão.')
    rows = []
    pattern = re.compile(r'(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<description>.+?)\s+(?P<amount>-?[\d.]+,\d{2})(?:\s+(?P<direction>entrada|sa[ií]da|cr[eé]dito|d[eé]bito))?$', re.I)
    for number, line in enumerate(text.splitlines(), 1):
        match = pattern.search(line.strip())
        if match:
            rows.append(normalize_row(number, **match.groupdict()))
    if not rows:
        raise ValidationError('Layout textual do PDF não reconhecido.')
    return rows


def parse_cnab(data):
    lines = [line.rstrip('\r') for line in decode_text(data).splitlines() if line.strip()]
    lengths = {len(line) for line in lines}
    if not lines or lengths not in ({240}, {400}):
        raise ValidationError('CNAB deve possuir exclusivamente linhas de 240 ou 400 posições.')
    width = next(iter(lengths))
    if width == 240:
        valid_envelope = lines[0][7:8] == '0' and lines[-1][7:8] == '9'
        bank = lines[0][:3]
    else:
        valid_envelope = lines[0][:1] == '0' and lines[-1][:1] == '9'
        bank = lines[0][76:79]
    if not valid_envelope:
        raise ValidationError('Cabeçalho ou trailer CNAB não reconhecido.')
    if bank not in {'001', '033', '104', '237', '341', '756'}:
        raise ValidationError('Banco CNAB não reconhecido com segurança.')
    rows = []
    for number, line in enumerate(lines[1:-1], 2):
        if width == 240 and len(line) == 240 and line[13:14] == 'T':
            raw_amount = line[81:96]
            amount = Decimal(raw_amount) / 100 if raw_amount.isdigit() else raw_amount
            rows.append(normalize_row(number, line[73:81], line[37:57].strip() or f'Movimentação CNAB {number}', amount, FinancialTransaction.Direction.INFLOW, line[62:73].strip()))
        elif width == 400 and len(line) == 400 and line[:1] == '1':
            raw_amount = line[126:139]
            amount = Decimal(raw_amount) / 100 if raw_amount.isdigit() else raw_amount
            rows.append(normalize_row(number, line[110:116], line[37:62].strip() or f'Movimentação CNAB {number}', amount, FinancialTransaction.Direction.INFLOW, line[62:70].strip()))
    if not rows:
        raise ValidationError('Versão ou segmento CNAB não reconhecido com segurança.')
    return rows


PARSERS = {'csv': parse_csv, 'xls': parse_xls, 'ofx': parse_ofx, 'pdf': parse_pdf, 'cnab': parse_cnab}


def parse_file(file_format, data, options=None):
    rows = PARSERS[file_format](data, options) if file_format in {'csv', 'xls'} else PARSERS[file_format](data)
    if not rows:
        raise ValidationError('O arquivo não contém movimentações.')
    if len(rows) > settings.FINVIEW_IMPORT_MAX_ROWS:
        raise ValidationError(f'O arquivo excede o limite de {settings.FINVIEW_IMPORT_MAX_ROWS} linhas.')
    return rows


def row_fingerprint(business_id, row):
    raw = f'{business_id}|{row.date}|{row.description.lower()}|{row.amount}|{row.direction}'
    return hashlib.sha256(raw.encode()).hexdigest()


def create_batch(*, business, user, uploaded_file, mapping=None):
    if uploaded_file.size <= 0:
        raise ValidationError('O arquivo está vazio.')
    if uploaded_file.size > settings.FINVIEW_IMPORT_MAX_BYTES:
        raise ValidationError('O arquivo excede o limite de 10 MiB.')
    data = uploaded_file.read()
    file_hash = hashlib.sha256(data).hexdigest()
    if ImportBatch.objects.filter(business=business, file_hash=file_hash).exists():
        raise ValidationError('Este arquivo já foi enviado para a empresa.')
    file_format = detect_format(uploaded_file.name)
    rows = parse_file(file_format, data, mapping)
    with transaction.atomic():
        batch = ImportBatch.objects.create(business=business, uploaded_by=user, original_name=sanitize_filename(uploaded_file.name), file_format=file_format, file_hash=file_hash, file_size=len(data), status=ImportBatch.Status.VALIDATING)
        batch.stored_file.save(batch.original_name, ContentFile(data), save=False)
        fingerprints = []
        objects = []
        for row in rows:
            fingerprint = row_fingerprint(business.id, row)
            fingerprints.append(fingerprint)
            duplicate = FinancialTransaction.objects.filter(business=business, date=row.date, amount=row.amount, direction=row.direction, name__iexact=row.description).exists() if not row.errors else False
            objects.append(ImportRow(batch=batch, row_number=row.row_number, date=row.date, description=row.description, amount=row.amount, direction=row.direction, external_identifier=row.external_identifier, fingerprint=fingerprint, validation_status=ImportRow.ValidationStatus.INVALID if row.errors else ImportRow.ValidationStatus.VALID, validation_errors=row.errors, possible_duplicate=duplicate, decision=ImportRow.Decision.PENDING if row.errors else ImportRow.Decision.INCLUDE))
        ImportRow.objects.bulk_create(objects)
        batch.total_rows = len(objects)
        batch.valid_rows = sum(not item.validation_errors for item in objects)
        batch.invalid_rows = len(objects) - batch.valid_rows
        batch.duplicate_rows = sum(item.possible_duplicate for item in objects)
        batch.status = ImportBatch.Status.AWAITING_REVIEW
        batch.save()
    suggest_categories(batch)
    return batch


def suggest_categories(batch):
    rows = list(batch.rows.filter(validation_status=ImportRow.ValidationStatus.VALID, suggested_category__isnull=True)[:100])
    categories = list(ManagerialCategory.objects.filter(business=batch.business, is_active=True).values('id', 'name'))
    if not rows or not categories:
        return
    try:
        suggestions = classificar_descricoes([row.description for row in rows], categories)
    except Exception:
        return
    category_map = {item.id: item for item in ManagerialCategory.objects.filter(business=batch.business)}
    for suggestion in suggestions:
        row = rows[suggestion['index']]
        row.suggested_category = category_map.get(suggestion['category_id'])
        row.classification_confidence = Decimal(str(suggestion['confidence']))
        row.save(update_fields=['suggested_category', 'classification_confidence', 'updated_at'])


def remove_raw_file(batch):
    if batch.stored_file:
        batch.stored_file.delete(save=False)
        batch.stored_file = ''


def confirm_batch(batch, user):
    if batch.status == ImportBatch.Status.PROCESSED:
        return 0
    created = 0
    with transaction.atomic():
        locked = ImportBatch.objects.select_for_update().get(pk=batch.pk)
        if locked.status == ImportBatch.Status.PROCESSED:
            return 0
        for row in locked.rows.select_related('confirmed_category', 'suggested_category'):
            if row.decision != ImportRow.Decision.INCLUDE or row.validation_status != ImportRow.ValidationStatus.VALID or row.possible_duplicate:
                continue
            category = row.confirmed_category
            if category is None or category.business_id != locked.business_id:
                continue
            _, was_created = FinancialTransaction.objects.get_or_create(import_row=row, defaults={'business': locked.business, 'created_by': user, 'direction': row.direction, 'name': row.description, 'amount': row.amount, 'date': row.date, 'category': category, 'status': FinancialTransaction.Status.REALIZED, 'certainty': FinancialTransaction.Certainty.CONFIRMED, 'source': FinancialTransaction.Source.IMPORT})
            created += int(was_created)
        locked.status = ImportBatch.Status.PROCESSED if created else ImportBatch.Status.PARTIALLY_PROCESSED
        locked.finalized_at = timezone.now()
        remove_raw_file(locked)
        locked.save()
    return created
