CREATE TABLE IF NOT EXISTS source_run_log (
    run_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    job_name TEXT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    status TEXT NOT NULL,
    rows_read INTEGER DEFAULT 0,
    rows_written INTEGER DEFAULT 0,
    error_message TEXT,
    params_json TEXT
);

CREATE TABLE IF NOT EXISTS global_anchor_security (
    symbol TEXT NOT NULL,
    market TEXT NOT NULL,
    company_name TEXT NOT NULL,
    country TEXT,
    currency TEXT,
    industry_layer TEXT,
    chain_segment TEXT,
    is_core_anchor BOOLEAN DEFAULT FALSE,
    related_a_share_segments TEXT,
    related_a_share_symbols TEXT,
    source TEXT,
    updated_at TIMESTAMP,
    PRIMARY KEY(symbol, market)
);

CREATE TABLE IF NOT EXISTS global_anchor_price_daily (
    trade_date DATE NOT NULL,
    symbol TEXT NOT NULL,
    market TEXT NOT NULL,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    pre_close DOUBLE,
    pct_chg DOUBLE,
    volume DOUBLE,
    amount DOUBLE,
    relative_strength_5d DOUBLE,
    relative_strength_20d DOUBLE,
    source TEXT,
    ingested_at TIMESTAMP,
    PRIMARY KEY(trade_date, symbol, market)
);

CREATE TABLE IF NOT EXISTS global_anchor_manual_price_import (
    import_id TEXT PRIMARY KEY,
    source_file TEXT,
    market TEXT,
    imported_at TIMESTAMP,
    row_count INTEGER,
    checksum TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS taiwan_monthly_revenue (
    revenue_month TEXT NOT NULL,
    symbol TEXT NOT NULL,
    company_name TEXT,
    revenue DOUBLE,
    revenue_mom DOUBLE,
    revenue_yoy DOUBLE,
    cumulative_revenue DOUBLE,
    cumulative_yoy DOUBLE,
    source TEXT,
    ingested_at TIMESTAMP,
    PRIMARY KEY(revenue_month, symbol)
);

CREATE TABLE IF NOT EXISTS taiwan_institutional_flow (
    trade_date DATE NOT NULL,
    symbol TEXT NOT NULL,
    investor_type TEXT NOT NULL,
    buy_shares DOUBLE,
    sell_shares DOUBLE,
    net_shares DOUBLE,
    source TEXT,
    ingested_at TIMESTAMP,
    PRIMARY KEY(trade_date, symbol, investor_type)
);

CREATE TABLE IF NOT EXISTS us_sec_filing_event (
    accession_number TEXT PRIMARY KEY,
    cik TEXT NOT NULL,
    symbol TEXT,
    company_name TEXT,
    form_type TEXT,
    filing_date DATE,
    report_date DATE,
    filing_url TEXT,
    raw_path TEXT,
    extracted_text_path TEXT,
    key_items_json TEXT,
    keywords_json TEXT,
    impact_segments TEXT,
    sentiment_score DOUBLE,
    ingested_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS us_sec_company_fact (
    fact_id TEXT PRIMARY KEY,
    cik TEXT NOT NULL,
    symbol TEXT,
    company_name TEXT,
    metric_name TEXT NOT NULL,
    xbrl_tag TEXT,
    unit TEXT,
    period_end DATE,
    filed_date DATE,
    fiscal_year TEXT,
    fiscal_period TEXT,
    form_type TEXT,
    value DOUBLE,
    source TEXT,
    ingested_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS korea_disclosure_event (
    rcept_no TEXT PRIMARY KEY,
    corp_code TEXT,
    stock_code TEXT,
    corp_name TEXT,
    report_nm TEXT,
    rcept_dt DATE,
    rm TEXT,
    raw_url TEXT,
    raw_path TEXT,
    key_items_json TEXT,
    impact_segments TEXT,
    ingested_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS korea_corp_code_master (
    corp_code TEXT PRIMARY KEY,
    stock_code TEXT,
    corp_name TEXT,
    modify_date TEXT,
    source TEXT,
    ingested_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS industry_cycle_metric (
    metric_date DATE NOT NULL,
    metric_type TEXT NOT NULL,
    segment TEXT NOT NULL,
    value DOUBLE,
    unit TEXT,
    source TEXT,
    yoy DOUBLE,
    mom DOUBLE,
    z_score DOUBLE,
    interpretation TEXT,
    ingested_at TIMESTAMP,
    PRIMARY KEY(metric_date, metric_type, segment, source)
);

CREATE TABLE IF NOT EXISTS ai_chain_segment (
    segment_id TEXT PRIMARY KEY,
    segment_name TEXT NOT NULL,
    parent_segment TEXT,
    cycle_stage TEXT,
    bottleneck_level DOUBLE,
    technology_generation TEXT,
    upstream_segments TEXT,
    downstream_segments TEXT,
    key_global_anchors TEXT,
    key_a_share_symbols TEXT,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS a_share_chain_mapping (
    ts_code TEXT NOT NULL,
    name TEXT,
    segment TEXT NOT NULL,
    sub_segment TEXT,
    product TEXT,
    global_anchor_links TEXT,
    purity_level TEXT,
    purity_score DOUBLE,
    revenue_exposure DOUBLE,
    gross_margin DOUBLE,
    gross_margin_trend TEXT,
    customer_evidence TEXT,
    order_evidence TEXT,
    source_evidence TEXT,
    is_core BOOLEAN,
    is_second_order BOOLEAN,
    is_concept_only BOOLEAN,
    notes TEXT,
    version_id TEXT,
    is_latest BOOLEAN DEFAULT TRUE,
    evidence_level TEXT,
    source_url TEXT,
    claim TEXT,
    counter_evidence_text TEXT,
    key_validation_metrics TEXT,
    domestic_substitution TEXT,
    nvidia_relation TEXT,
    mass_production_status TEXT,
    confidence_score DOUBLE,
    last_verified_at TIMESTAMP,
    PRIMARY KEY(ts_code, segment, sub_segment)
);

CREATE TABLE IF NOT EXISTS a_share_chain_mapping_history (
    version_id TEXT NOT NULL,
    ts_code TEXT NOT NULL,
    name TEXT,
    segment TEXT NOT NULL,
    sub_segment TEXT,
    product TEXT,
    global_anchor_links TEXT,
    purity_level TEXT,
    revenue_exposure DOUBLE,
    gross_margin DOUBLE,
    gross_margin_trend TEXT,
    customer_evidence TEXT,
    order_evidence TEXT,
    source_evidence TEXT,
    is_core BOOLEAN,
    is_second_order BOOLEAN,
    is_concept_only BOOLEAN,
    notes TEXT,
    evidence_level TEXT,
    source_url TEXT,
    claim TEXT,
    counter_evidence_text TEXT,
    key_validation_metrics TEXT,
    domestic_substitution TEXT,
    nvidia_relation TEXT,
    mass_production_status TEXT,
    confidence_score DOUBLE,
    last_verified_at TIMESTAMP,
    is_latest BOOLEAN DEFAULT TRUE,
    PRIMARY KEY(version_id, ts_code, segment, sub_segment)
);

CREATE TABLE IF NOT EXISTS a_share_chain_mapping_version (
    version_id TEXT PRIMARY KEY,
    source_file TEXT NOT NULL,
    imported_at TIMESTAMP NOT NULL,
    row_count INTEGER,
    checksum TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS a_share_market_confirmation (
    trade_date DATE NOT NULL,
    ts_code TEXT NOT NULL,
    segment TEXT,
    pct_chg DOUBLE,
    turnover_rate DOUBLE,
    amount DOUBLE,
    volume_ratio DOUBLE,
    auction_strength DOUBLE,
    limit_status TEXT,
    dragon_tiger_net_buy DOUBLE,
    institution_net_buy DOUBLE,
    moneyflow_score DOUBLE,
    margin_score DOUBLE,
    trend_score DOUBLE,
    confirmation_score DOUBLE,
    source TEXT,
    ingested_at TIMESTAMP,
    PRIMARY KEY(trade_date, ts_code, segment)
);

CREATE TABLE IF NOT EXISTS a_share_announcement_event (
    ann_id TEXT PRIMARY KEY,
    ann_date DATE NOT NULL,
    ts_code TEXT NOT NULL,
    name TEXT,
    title TEXT,
    url TEXT,
    source TEXT,
    ingested_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS a_share_research_report_event (
    report_id TEXT PRIMARY KEY,
    trade_date DATE NOT NULL,
    ts_code TEXT,
    name TEXT,
    title TEXT,
    report_type TEXT,
    author TEXT,
    inst_csname TEXT,
    ind_name TEXT,
    url TEXT,
    source TEXT,
    ingested_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS a_share_report_rating_event (
    rating_id TEXT PRIMARY KEY,
    report_date DATE NOT NULL,
    ts_code TEXT,
    name TEXT,
    report_title TEXT,
    report_type TEXT,
    classify TEXT,
    org_name TEXT,
    author_name TEXT,
    quarter TEXT,
    op_rt DOUBLE,
    op_pr DOUBLE,
    tp DOUBLE,
    np DOUBLE,
    eps DOUBLE,
    pe DOUBLE,
    rd DOUBLE,
    roe DOUBLE,
    ev_ebitda DOUBLE,
    rating TEXT,
    max_price DOUBLE,
    min_price DOUBLE,
    source TEXT,
    ingested_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS theme_opportunity_score (
    score_date DATE NOT NULL,
    segment TEXT NOT NULL,
    industry_score DOUBLE,
    bottleneck_score DOUBLE,
    global_anchor_score DOUBLE,
    earnings_order_price_score DOUBLE,
    a_share_mapping_score DOUBLE,
    a_share_confirmation_score DOUBLE,
    crowding_score DOUBLE,
    risk_score DOUBLE,
    confidence_score DOUBLE,
    final_score DOUBLE,
    stage TEXT,
    conclusion TEXT,
    evidence_json TEXT,
    invalid_conditions_json TEXT,
    created_at TIMESTAMP,
    PRIMARY KEY(score_date, segment)
);

CREATE TABLE IF NOT EXISTS daily_ai_chain_briefing (
    briefing_date DATE PRIMARY KEY,
    global_chain_conclusion TEXT,
    top_segments_json TEXT,
    next_watch_segments_json TEXT,
    a_share_confirmed_segments_json TEXT,
    risk_segments_json TEXT,
    action_suggestion TEXT,
    evidence_json TEXT,
    invalid_conditions_json TEXT,
    markdown_path TEXT,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evidence_registry (
    evidence_id TEXT PRIMARY KEY,
    evidence_date DATE,
    source_type TEXT NOT NULL,
    source_name TEXT,
    source_url TEXT,
    source_file TEXT,
    source_title TEXT,
    entity_type TEXT,
    entity_id TEXT,
    entity_name TEXT,
    segment TEXT,
    sub_segment TEXT,
    evidence_level TEXT,
    claim TEXT NOT NULL,
    excerpt TEXT,
    numeric_value DOUBLE,
    numeric_unit TEXT,
    confidence DOUBLE,
    is_positive BOOLEAN,
    is_counter_evidence BOOLEAN DEFAULT FALSE,
    ingested_at TIMESTAMP,
    verified_by TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS signal_review_result (
    review_id TEXT PRIMARY KEY,
    signal_date DATE NOT NULL,
    review_date DATE NOT NULL,
    segment TEXT NOT NULL,
    original_stage TEXT,
    original_score DOUBLE,
    forward_return_1d DOUBLE,
    forward_return_3d DOUBLE,
    forward_return_5d DOUBLE,
    forward_return_10d DOUBLE,
    max_drawdown DOUBLE,
    was_confirmed BOOLEAN,
    was_false_positive BOOLEAN,
    was_false_negative BOOLEAN,
    review_comment TEXT,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS signal_review_summary (
    summary_id TEXT PRIMARY KEY,
    review_date DATE NOT NULL,
    segment TEXT NOT NULL,
    sample_count INTEGER,
    true_positive INTEGER,
    false_positive INTEGER,
    false_negative INTEGER,
    precision DOUBLE,
    recall DOUBLE,
    avg_forward_return_3d DOUBLE,
    avg_forward_return_10d DOUBLE,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS counter_evidence_rule (
    rule_id TEXT PRIMARY KEY,
    segment TEXT,
    rule_name TEXT,
    rule_type TEXT,
    condition_expr TEXT,
    severity TEXT,
    description TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS segment_market_confirmation_daily (
    trade_date DATE NOT NULL,
    segment TEXT NOT NULL,
    segment_return_1d DOUBLE,
    segment_return_5d DOUBLE,
    segment_vs_all_a_5d DOUBLE,
    core_pool_hit_rate DOUBLE,
    limit_up_count INTEGER,
    limit_up_amount DOUBLE,
    top_list_net_buy DOUBLE,
    institution_net_buy DOUBLE,
    moneyflow_large_net DOUBLE,
    margin_balance_delta DOUBLE,
    turnover_zscore DOUBLE,
    crowding_score DOUBLE,
    confirmation_score DOUBLE,
    stage TEXT,
    created_at TIMESTAMP,
    PRIMARY KEY(trade_date, segment)
);

CREATE TABLE IF NOT EXISTS data_quality_report (
    report_id TEXT PRIMARY KEY,
    report_date DATE NOT NULL,
    source TEXT NOT NULL,
    job_name TEXT NOT NULL,
    status TEXT NOT NULL,
    rows_read INTEGER DEFAULT 0,
    rows_written INTEGER DEFAULT 0,
    note TEXT,
    created_at TIMESTAMP
);
