def review_inputs(run: dict, outputs: dict) -> dict:
    """Project review data without truncating claims, risks or source excerpts."""
    evidence = [
        {key: value for key, value in item.items() if key not in ('related_claim', 'document_id')}
        for item in run['evidence']
    ]
    previous = {
        stage: {key: value for key, value in output.items() if value not in (None, [], {})}
        for stage, output in outputs.items()
    }
    return {
        'untrusted_evidence': evidence,
        'python_metrics': run['metrics'],
        'previous_outputs': previous,
        'validation_findings': list(dict.fromkeys(run['review']['findings'])),
        'metric_issues': run['review'].get('metric_issues', []),
        'review_context_policy': (
            '仅去除证据 related_claim/document_id 与历史空字段；证据片段、ID、来源、'
            '全部 claims/risks/summary/验收条件/未解决问题保留，未截断。'
            '指标告警为阻断项；unknown_metric 是目录缺失，不等于已证明算术错误；'
            'missing_reference 是引用缺失；value_mismatch 是声明值与目录值不一致。'
            '应检查单位、分组和分母，不能无依据批准。'
        ),
    }
