import hashlib
import io
import json
from pathlib import Path

from pypdf import PdfReader
from .config import safe_text, public_data


def source_units(filename: str, data: bytes, text: str, rows: list[dict]) -> list[dict]:
    if Path(filename).suffix.lower() == '.pdf':
        reader = PdfReader(io.BytesIO(data))
        return [{'location': f'page:{i + 1}', 'excerpt': (page.extract_text() or '')[:2000]}
                for i, page in enumerate(reader.pages[:80]) if page.extract_text()]
    if rows:
        return [{'location': f'record:{i + 1}', 'excerpt': row, 'supplier': row.get('supplier', '')}
                for i, row in enumerate(rows[:100])]
    return [{'location': f'line:{i + 1}', 'excerpt': line[:2000]}
            for i, line in enumerate(text.splitlines()[:100]) if line.strip()]


def make_evidence(documents: list[dict], metrics: dict | None) -> list[dict]:
    records = []
    for doc in documents:
        units = doc.get('units') or [{'location': 'text:excerpt', 'excerpt': doc.get('text', '')[:1000]}]
        for unit in units:
            digest = hashlib.sha256(f"{doc.get('id', doc['name'])}:{unit['location']}".encode()).hexdigest()[:10]
            records.append({
                'evidence_id': f'E-{digest}', 'source_file': doc['name'], 'document_id': doc.get('id'),
                'source_location': unit['location'], 'supporting_excerpt': unit['excerpt'],
                'related_claim': [], 'verification_status': 'verified', 'kind': 'fact',
                'supplier': unit.get('supplier', ''), 'risk_type': 'source', 'demo_data': doc.get('demo', False),
            })
    if metrics:
        for key in ('count', 'spend', 'on_time', 'defect'):
            records.append({
                'evidence_id': f'M-{key}', 'source_file': metrics['source'],
                'source_location': 'parsed records / Python aggregate',
                'supporting_excerpt': {'metric': key, 'value': metrics[key], 'method': 'sum' if key == 'spend' else 'count' if key == 'count' else 'unweighted mean'},
                'related_claim': [], 'verification_status': 'verified', 'kind': 'computed',
                'supplier': '', 'risk_type': 'metric',
                'demo_data': any(d.get('demo') and d['name'] == metrics['source'] for d in documents),
            })
    return json.loads(safe_text(json.dumps(records, ensure_ascii=False)))


def validate_references(result: dict, evidence: list[dict], metric_issues: list[dict] | None = None) -> list[str]:
    lookup = {item['evidence_id']: item for item in evidence}
    findings = []
    for claim_index, item in enumerate(result.get('claims', [])):
        references = item['evidence_ids']
        if any(ref not in lookup for ref in references):
            findings.append(f"错误引用：{item['text'][:120]}")
        if item['kind'] in ('fact', 'computed') and not references:
            findings.append(f"结论缺少证据：{item['text'][:120]}")
        if item['kind'] in ('fact', 'computed') and any(lookup.get(ref, {}).get('kind') in ('hypothesis', 'external_unverified') for ref in references):
            findings.append(f"结论缺少证据：不能把模型假设当作已验证事实。{item['text'][:80]}")
        if item['kind'] == 'computed' and references and not any(lookup.get(ref, {}).get('kind') == 'computed' for ref in references):
            findings.append(f"数值结论未引用 Python 指标：{item['text'][:100]}")
        if item['kind'] == 'computed':
            values = item.get('metric_values', {})
            if not values:
                findings.append(f"数值结论缺少可校验值：{item['text'][:100]}")
            for metric, value in values.items():
                ref = f'M-{metric}'
                record = lookup.get(ref)
                actual = record.get('supporting_excerpt', {}) if record else {}
                codes = []
                if record is None:
                    codes.append('unknown_metric')
                else:
                    if ref not in references:
                        codes.append('missing_reference')
                    if not isinstance(actual, dict) or 'value' not in actual:
                        codes.append('invalid_metric_evidence')
                    elif actual['value'] != value:
                        codes.append('value_mismatch')
                for code in codes:
                    # Preserve legacy summary wording; add explicit machine-readable diagnostics.
                    findings.append(safe_text(f"数值冲突：{metric} 未匹配 Python 指标。 [{code}]"))
                    if metric_issues is not None:
                        metric_issues.append(public_data({
                            'type': code, 'metric': metric, 'claim_index': claim_index,
                            'observed_value': value,
                            'expected_value': actual.get('value') if isinstance(actual, dict) else None,
                            'expected_evidence_id': ref, 'referenced_evidence_ids': list(references),
                            'blocking': True,
                        }))
        for ref in references:
            if ref in lookup and item['text'] not in lookup[ref]['related_claim']:
                lookup[ref]['related_claim'].append(item['text'])
    for item in result.get('risks', []):
        for ref in item['evidence_ids']:
            if ref in lookup:
                lookup[ref]['risk_type'] = 'delivery_quality'
                if item['reason'] not in lookup[ref]['related_claim']:
                    lookup[ref]['related_claim'].append(item['reason'])
    for item in result.get('risks', []) + result.get('actions', []):
        if not item['evidence_ids']:
            findings.append('风险或行动缺少证据。')
        if any(ref not in lookup for ref in item['evidence_ids']):
            findings.append('风险或行动包含不存在的证据引用。')
    for finding in findings:
        if '错误引用' in finding or '数值冲突' in finding:
            evidence.append({'evidence_id': f'C-{len(evidence)}', 'source_file': 'Model claim validation',
                'source_location': 'output contract / not a source quote', 'supporting_excerpt': finding,
                'related_claim': [finding], 'verification_status': 'conflict', 'kind': 'hypothesis',
                'supplier': '', 'risk_type': 'citation', 'demo_data': False})
    return list(dict.fromkeys(findings))
