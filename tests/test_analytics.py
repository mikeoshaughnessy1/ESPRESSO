"""Tests use a tiny made-up table so you can check every answer by hand."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import agent  # noqa: E402
import analytics  # noqa: E402


@pytest.fixture
def df():
    return pd.DataFrame({
        'store': ['A', 'A', 'B', 'B', 'B'],
        'channel': ['web', 'shop', 'web', 'shop', 'shop'],
        'amount': [100, 200, 50, None, 150],
    })


def test_total_all_rows(df):
    r = analytics.get_total(df, 'amount')
    assert r.value == 500 and r.rows_used == 4
    assert any('missing' in c for c in r.caveats)


def test_total_filtered(df):
    assert analytics.get_total(df, 'amount', {'store': 'A'}).value == 300


def test_unknown_filter_value_returns_error_not_zero(df):
    r = analytics.get_total(df, 'amount', {'store': 'Z'})
    assert r.error and r.value is None


def test_group_total(df):
    assert analytics.group_total(df, 'amount', 'store').value == {'A': 300.0, 'B': 200.0}


def test_data_quality(df):
    r = analytics.data_quality_report(df)
    assert r.value['columns_with_missing'] == {'amount': 1}


def test_merge_without_fan_out(df):
    stores = pd.DataFrame({'store': ['A', 'B'], 'city': ['X', 'Y']})
    _, rep = analytics.check_merge(df, stores, on='store', value_col='amount')
    assert not rep['changed']


def test_merge_fan_out_is_detected(df):
    dup = pd.DataFrame({'store': ['A', 'A', 'B'], 'city': ['X', 'X2', 'Y']})
    _, rep = analytics.check_merge(df, dup, on='store', value_col='amount')
    assert rep['changed'] and rep['sum_after'] > rep['sum_before']


def test_dispatcher_rejects_unknown_tool_and_arguments(df):
    log = []
    assert agent.run_tool('run_python', {}, df, log).error
    assert agent.run_tool('get_total', {'value_col': 'amount', 'code': 'x'}, df, log).error


def test_unsupported_question(df):
    out = agent.answer_question('What is the meaning of life?', df)
    assert 'cannot answer' in out['findings']


# ------------------------------------------------ E-Presso revenue tools
import config as C  # noqa: E402
import data_prep  # noqa: E402


@pytest.fixture
def sales():
    """8 line items, 2 years, 2 stores, 2 channels. Totals are easy by hand:
    2027 = 100+200+300+400 = 1000, 2028 = 150+250+250+350 = 1000 (+ a blank)."""
    raw = pd.DataFrame({
        C.DATE: ['2027-01-05', '2027-01-20', '2027-02-10', '2027-02-11',
                 '2028-01-05', '2028-01-20', '2028-02-10', '2028-02-11', '2028-03-01'],
        C.REVENUE: [100, 200, 300, 400, 150, 250, 250, 350, None],
        C.CHANNEL: ['Website', 'Store', 'Website', 'Store',
                    'Website', 'Store', 'Website', 'Store', 'Store'],
        C.STORE: ['Chicago', 'Chicago', 'Denver', 'Denver',
                  'Chicago', 'Chicago', 'Denver', 'Denver', 'Denver'],
    })
    return data_prep.add_dates(raw)


def test_total_revenue(sales):
    r = analytics.get_total_revenue(sales)
    assert r.value == 2000 and r.rows_used == 8


def test_total_revenue_filtered(sales):
    assert analytics.get_total_revenue(sales, {C.YEAR: 2028, C.CHANNEL: 'Website'}).value == 400


def test_revenue_by_channel_shares_add_to_100(sales):
    v = analytics.get_revenue_by(sales, C.CHANNEL).value
    assert v['Website']['revenue'] == 800 and v['Store']['revenue'] == 1200
    assert v['Website']['share_pct'] + v['Store']['share_pct'] == 100


def test_growth_by_store(sales):
    v = analytics.get_growth(sales, C.STORE).value
    assert v['Chicago']['pct_change'] == pytest.approx(33.33, abs=0.01)  # 300 -> 400
    assert v['Denver']['pct_change'] == pytest.approx(-14.29, abs=0.01)  # 700 -> 600


def test_growth_needs_two_years(sales):
    assert analytics.get_growth(sales, C.STORE, {C.YEAR: 2027}).error


def test_monthly_share_denominator_is_the_year(sales):
    v = analytics.get_monthly_share(sales, 2027).value
    assert v[1]['share_pct'] == 30 and v[2]['share_pct'] == 70


def test_thousand_dollar_test(sales):
    """Same function, modified data: total rises by exactly 1000."""
    before = analytics.get_total_revenue(sales).value
    changed = sales.copy()
    changed.loc[0, C.REVENUE] += 1000
    assert analytics.get_total_revenue(changed).value == before + 1000


def test_router_picks_tools(sales):
    assert agent.rules_router('Revenue by channel in 2028?', sales)[1:] == \
        ('get_revenue_by', {'group': C.CHANNEL, 'filters': {C.YEAR: 2028}})
    assert agent.rules_router('Which store had the biggest decline?', sales)[1] == 'get_growth'


def test_profit_question_flags_limit(sales):
    out = agent.answer_question('Which store is the most profitable?', sales)
    assert 'not profit' in out['interpretation'] or 'profit cannot' in out['findings']


def test_llm_mode_without_key_falls_back(sales):
    out = agent.answer_question('total revenue', sales, mode='llm', api_key=None)
    assert out['mode'] == 'Rules-based' and 'No API key' in out['note']


def test_unknown_store_is_an_error_not_a_guess(sales):
    assert analytics.get_total_revenue(sales, {C.STORE: 'Bozeman'}).error


# ---------------------------------------- fixes found by stress-testing
def test_partial_last_year_is_flagged(sales):
    extra = sales.iloc[:1].assign(**{C.DATE: pd.Timestamp('2029-01-31')})
    extra = data_prep.add_dates(extra)
    r = analytics.get_growth(pd.concat([sales, extra]), C.STORE)
    assert any(c.startswith('Partial year') for c in r.caveats)


def test_percent_question_returns_shares(sales):
    assert agent.rules_router('What percent of revenue came from the website in 2028?', sales)[1:] == \
        ('get_revenue_by', {'group': C.CHANNEL, 'filters': {C.YEAR: 2028}})


def test_two_stores_are_both_matched(sales):
    _, tool, args = agent.rules_router('Compare Chicago and Denver revenue', sales)
    assert sorted(args['filters'][C.STORE]) == ['Chicago', 'Denver'] or tool == 'get_growth'


def test_data_clean_question_goes_to_quality_report(sales):
    assert agent.rules_router('Is the data clean?', sales)[1] == 'data_quality_report'


def test_missing_revenue_column_gives_message_not_crash():
    out = data_prep.build_sales_table({'sales.csv': pd.DataFrame({'Date': ['2025-01-31'], 'Store ID': ['SH01']})})
    assert out['sales'] is None and any('Revenue' in p for p in out['problems'])


def test_assignment_test2_wording_routes_to_growth(sales):
    """Live-app bug: 'percentage' sent this to the share breakdown instead of growth."""
    q = 'Which store experienced the greatest percentage revenue decline?'
    assert agent.rules_router(q, sales)[1] == 'get_growth'
    assert 'Largest decline' in agent.answer_question(q, sales)['findings']
