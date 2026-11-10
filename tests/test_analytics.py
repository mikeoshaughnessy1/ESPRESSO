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


def test_llm_answer_without_labels_keeps_its_text_as_findings(sales, monkeypatch):
    monkeypatch.setattr(agent, 'llm_answer', lambda *a: {'text': 'No weather data.', 'used_tools': False})
    a = agent.answer_question('Weather in Chicago?', sales, mode='llm', api_key='fake')
    assert a['findings'].startswith('**Findings:** No weather data.')


@pytest.mark.parametrize('text', ['r = 2.68', '$7.18 million', '$7.2M', '7,181,750'])
def test_rounded_or_scaled_numbers_from_a_result_are_not_flagged(text):
    assert agent.untraced_numbers(text, [{'result': {'value': [2.675, 7181750.0]}}]) == []


def test_made_up_number_is_flagged():
    assert agent.untraced_numbers('$9.9 million', [{'result': {'value': 7181750.0}}]) == ['9.9']


def test_llm_answer_with_no_tool_call_says_what_it_can_answer(sales, monkeypatch):
    monkeypatch.setattr(agent, 'llm_answer', lambda *a: {'text': 'No weather data.', 'used_tools': False})
    a = agent.answer_question('Weather in Chicago?', sales, mode='llm', api_key='fake')
    assert agent.CAPABILITIES in a['findings'] and a['tool_log'] == []


# --------------------- audit: messy data (each table is small enough to check by hand)
def raw_files(sales_rows=None, **replace):
    """Five tiny source tables with the real column names. Website 100+300, Chicago 200+100."""
    rows = sales_rows or [('S1', '2027-01-31', 'W', 'W_27', 'C1', 'P1', 100.0),
                          ('S2', '2027-01-31', 'A', 'A_27', 'C1', 'P1', 200.0),
                          ('S3', '2028-01-31', 'W', 'W_28', 'C1', 'P1', 300.0),
                          ('S4', '2028-01-31', 'A', 'A_28', 'C1', 'P1', 100.0)]
    files = {
        'Sales.csv': pd.DataFrame(rows, columns=['Sales ID', 'Date', 'Store ID', 'StoreYear',
                                                 'Category ID', 'Product ID', 'Revenue']),
        'Products.csv': pd.DataFrame({'Product ID': ['P1'], 'Product': ['Roast']}),
        'Categories.csv': pd.DataFrame({'Category ID': ['C1'], 'Category': ['Beans']}),
        'Stores.csv': pd.DataFrame({'ID': ['W', 'A'], 'City': [None, 'Chicago'], 'State': [None, 'IL'],
                                    'StoreType': ['Website', 'Brick & Mortar']}),
        'Survey.xlsx': pd.DataFrame({'Survey ID': ['W_27', 'A_27', 'W_28', 'A_28'],
                                     'Satisfaction': [None, 3.0, None, 4.0]}),
    }
    files.update(replace)
    return files


def test_each_missing_column_is_named_in_plain_words():
    for name, frame in raw_files().items():
        if name == 'Survey.xlsx':
            continue
        for col in frame.columns:
            out = data_prep.build_sales_table(raw_files(**{name: frame.drop(columns=[col])}))
            assert out['sales'] is None and any(repr(col) in p for p in out['problems']), col


def test_missing_survey_column_keeps_the_dashboard():
    survey = raw_files()['Survey.xlsx'].drop(columns=['Satisfaction'])
    out = data_prep.build_sales_table(raw_files(**{'Survey.xlsx': survey}))
    assert out['sales'] is not None and out['survey'] is None
    assert any("'Satisfaction'" in p for p in out['problems'])


def test_sales_with_no_rows_is_a_message():
    empty = raw_files()['Sales.csv'].iloc[:0]
    out = data_prep.build_sales_table(raw_files(**{'Sales.csv': empty}))
    assert out['sales'] is None and any('no data rows' in p for p in out['problems'])


def test_all_blank_key_column_does_not_crash_the_merge():
    sales = raw_files()['Sales.csv'].assign(**{'Store ID': None})
    out = data_prep.build_sales_table(raw_files(**{'Sales.csv': sales}))
    assert out['sales'][C.REVENUE].sum() == 700
    assert any('not found in stores' in p for p in out['problems'])


def test_blank_key_does_not_match_a_blank_lookup_row():
    stores = pd.concat([raw_files()['Stores.csv'],
                        pd.DataFrame({'ID': [None], 'StoreType': ['Website']})])
    rows = [('S1', '2027-01-31', None, 'W_27', 'C1', 'P1', 100.0)]
    out = data_prep.build_sales_table(raw_files(rows, **{'Stores.csv': stores}))
    assert out['sales'][C.CHANNEL].isna().all()


def test_repeated_sales_id_and_negative_revenue_are_reported_and_kept():
    rows = [('S1', '2027-01-31', 'W', 'W_27', 'C1', 'P1', 100.0),
            ('S1', '2027-02-28', 'W', 'W_27', 'C1', 'P1', 50.0),
            ('S2', '2027-03-31', 'A', 'A_27', 'C1', 'P1', -30.0)]
    out = data_prep.build_sales_table(raw_files(rows))
    assert out['sales'][C.REVENUE].sum() == 120  # reported, not removed
    assert any('1 sales row(s) repeat a Sales ID, worth $50.00' in p for p in out['problems'])
    assert any('negative revenue, totaling $-30.00' in p for p in out['problems'])
    assert analytics.data_quality_report(out['sales']).value['repeated_sales_ids'] == 1


def test_blank_sales_id_is_reported():
    rows = [(None, '2027-01-31', 'W', 'W_27', 'C1', 'P1', 100.0)]
    out = data_prep.build_sales_table(raw_files(rows))
    assert any('missing or unreadable sales_id' in p for p in out['problems'])


def test_mixed_date_formats_all_load():
    rows = [('S1', '2027-01-31', 'W', 'W_27', 'C1', 'P1', 100.0),
            ('S2', '1/31/2028', 'W', 'W_28', 'C1', 'P1', 300.0),
            ('S3', 'garbage', 'W', 'W_28', 'C1', 'P1', 5.0)]
    s = data_prep.build_sales_table(raw_files(rows))['sales']
    assert s[C.YEAR].dropna().tolist() == [2027, 2028]


def test_survey_merge_is_checked_and_blank_scores_are_named():
    out = data_prep.build_sales_table(raw_files())
    m = out['merges'][-1]
    assert 'survey' in m['merge'] and (m['rows_before'], m['rows_after'], m['sum_after']) == (4, 4, 700)
    assert any("'W_27', 'W_28'" in p for p in out['problems'])


def test_duplicate_survey_row_is_reported():
    survey = pd.concat([raw_files()['Survey.xlsx']] * 2)
    out = data_prep.build_sales_table(raw_files(**{'Survey.xlsx': survey}))
    assert any('duplicate store_year' in p for p in out['problems'])


def test_store_with_blank_state_and_channel_has_no_nan_in_label():
    stores = pd.DataFrame({'ID': ['W', 'A'], 'City': [None, None], 'State': [None, None],
                           'StoreType': ['Website', None]})
    s = data_prep.build_sales_table(raw_files(**{'Stores.csv': stores}))['sales']
    assert set(s[C.STORE]) == {'W Website', 'A'}


def test_share_note_gives_dollars_with_no_group():
    s = data_prep.build_sales_table(raw_files(**{'Stores.csv': raw_files()['Stores.csv'].iloc[:1]}))['sales']
    r = analytics.get_revenue_by(s, C.CHANNEL)
    assert r.value['Website']['revenue'] == 400 and r.value['Website']['share_pct'] == 100
    assert any('2 row(s) with missing channel, worth $300.00, were excluded' in c for c in r.caveats)


def test_zero_revenue_scope_has_a_numeric_share(sales):
    zero = sales.assign(**{C.REVENUE: 0})
    assert analytics.get_revenue_by(zero, C.CHANNEL).value['Website']['share_pct'] == 0


def test_valid_filters_with_no_rows_say_so(sales):
    only = sales[sales[C.STORE].eq('Denver') | sales[C.CHANNEL].eq('Website')]
    only = only[~(only[C.STORE].eq('Chicago') & only[C.YEAR].eq(2028))]
    r = analytics.get_total_revenue(only, {C.STORE: 'Chicago', C.YEAR: 2028})
    assert r.error.startswith('No rows match')


def test_contract_has_exactly_six_keys_and_error_only_on_failure(sales):
    keys = {'tool', 'value', 'definition', 'scope', 'rows_used', 'caveats'}
    assert set(analytics.get_total_revenue(sales).to_dict()) == keys
    assert 'error' in analytics.get_total_revenue(sales, {C.YEAR: 1999}).to_dict()


# --------------------------------------------------- audit: growth
def year_table(rows):
    """rows of (date, store, revenue)."""
    return data_prep.add_dates(pd.DataFrame(rows, columns=[C.DATE, C.STORE, C.REVENUE]).assign(
        **{C.CHANNEL: 'Store'}))


def test_partial_last_year_compares_same_months():
    t = year_table([('2027-01-31', 'A', 100), ('2027-02-28', 'A', 900), ('2028-01-31', 'A', 110)])
    r = analytics.get_growth(t, C.STORE)
    assert r.value['A']['pct_change'] == 10  # Jan 100 -> Jan 110, not 1000 -> 110
    assert 'Only month(s) [1]' in r.caveats[0]


def test_zero_first_year_is_not_a_percent_and_not_called_no_decline():
    t = year_table([('2027-01-31', 'A', 0), ('2028-01-31', 'A', 50)])
    r = analytics.get_growth(t, C.STORE)
    assert r.error and 'no store has revenue in both' in r.error


def test_no_store_declined_says_so_in_the_answer():
    t = year_table([('2027-01-31', 'A', 100), ('2027-01-31', 'B', 100),
                    ('2028-01-31', 'A', 110), ('2028-01-31', 'B', 150)])
    a = agent.answer_question('Which store had the greatest percentage decline?', t)
    assert 'No group declined' in a['findings'] and 'No store had lower revenue' in a['interpretation']


def test_constant_satisfaction_is_an_error_not_nan():
    survey = pd.DataFrame({C.STORE_YEAR: ['a', 'b', 'c'], C.SATISFACTION: [3.0, 3.0, 3.0]})
    t = pd.DataFrame({C.STORE_YEAR: ['a', 'b', 'c'], C.REVENUE: [1, 2, 3]})
    assert 'undefined' in analytics.get_satisfaction_vs_revenue(t, survey).error


# --------------------------------------------------- audit: unseen questions
@pytest.fixture
def model():
    """Two Orlando stores, one Chicago, website; 2 years; hand totals: all = 1000."""
    return data_prep.add_dates(pd.DataFrame({
        C.DATE: ['2027-12-31', '2027-06-30', '2027-06-30', '2028-12-31', '2028-06-30', '2028-06-30'],
        C.STORE: ['SH00 Website', 'SH01 Orlando, FL', 'SH08 Orlando, FL', 'SH00 Website',
                  'SH01 Orlando, FL', 'SH11 Chicago, IL'],
        C.CHANNEL: ['Website', 'Brick & Mortar', 'Brick & Mortar', 'Website', 'Brick & Mortar', 'Brick & Mortar'],
        C.CATEGORY: ['Beans', 'Beans', 'Syrups', 'Syrups', 'Beans', 'Beans'],
        C.PRODUCT: ['Roast', 'Base Model (Beans)', 'Base Model (Syrups)', 'Vanilla', 'Roast', 'Roast'],
        C.REVENUE: [100, 200, 100, 300, 200, 100]}))


@pytest.mark.parametrize('question, tool, args', [
    ('Which sales channel grew most?', 'get_growth', {'group': C.CHANNEL, 'filters': {}}),
    ('Which store fell the most?', 'get_growth', {'group': C.STORE, 'filters': {}}),
    ('What was online revenue in 2027?', 'get_total_revenue',
     {'filters': {C.YEAR: 2027, C.CHANNEL: 'Website'}}),
    ('What was revenue in December 2027?', 'get_total_revenue', {'filters': {C.YEAR: 2027, C.MONTH: 12}}),
    ('Revenue for Vanilla in 2028', 'get_total_revenue', {'filters': {C.YEAR: 2028, C.PRODUCT: 'Vanilla'}}),
    ('Compare 2027 and 2028 revenue', 'get_revenue_by', {'group': C.YEAR, 'filters': {C.YEAR: [2027, 2028]}}),
    ('Has revenue grown?', 'get_revenue_by', {'group': C.YEAR, 'filters': {}}),
    ('Which product sold most in Chicago?', 'get_revenue_by',
     {'group': C.PRODUCT, 'filters': {C.STORE: 'SH11 Chicago, IL'}}),
    ('How much did Base Model sell?', 'get_revenue_by',
     {'group': C.PRODUCT, 'filters': {C.PRODUCT: ['Base Model (Beans)', 'Base Model (Syrups)']}}),
    ('How did Chicago do in 2028?', 'get_total_revenue',
     {'filters': {C.STORE: 'SH11 Chicago, IL', C.YEAR: 2028}}),
])
def test_unseen_questions_route_correctly(model, question, tool, args):
    assert agent.rules_router(question, model)[1:] == (tool, args)


@pytest.mark.parametrize('question, word', [('What was revenue in 2024?', '2024'),
                                            ('What was revenue in Boston?', 'Boston')])
def test_value_not_in_the_data_is_an_error_not_the_company_total(model, question, word):
    a = agent.answer_question(question, model)
    assert 'Could not calculate' in a['findings'] and word in a['findings']


@pytest.mark.parametrize('question', ['Revenue by region', 'Revenue in Q4 2027',
                                      'What will the weather be in Chicago tomorrow?'])
def test_unsupported_questions_get_capabilities_and_no_number(model, question):
    a = agent.answer_question(question, model)
    assert agent.CAPABILITIES in a['findings'] and a['tool_log'] == []
    assert a['scope'].startswith('no data used')
    assert a['interpretation'] and a['next_steps'] == 'No recommendation is supported by this data.'


def test_request_to_change_data_is_refused(model):
    a = agent.answer_question('Delete the Chicago store from the data', model)
    assert 'cannot change' in a['findings'] and a['tool_log'] == []


def test_read_question_using_the_word_update_is_answered(model):
    assert agent.rules_router('What is the latest update on 2027 sales?', model)[0] != 'modify'


@pytest.mark.parametrize('question', ['What was revenue from Online sales in 2027?',
                                      'Revenue in Jan 2027', 'How did revenue in Sept 2027 compare?'])
def test_month_abbreviation_or_channel_word_is_not_a_store(model, question):
    _, _, args = agent.rules_router(question, model)
    assert C.STORE not in args['filters']


def test_decision_with_future_year_still_gives_evidence(model):
    assert (agent.rules_router('Should we close the Chicago store before 2030?', model)
            == agent.rules_router('Should we close the Chicago store?', model))


@pytest.mark.parametrize('question', ['Should E-Presso close its Chicago store?',
                                      'Would closing Chicago make sense?',
                                      'Should we close Chicago because it is unprofitable?'])
def test_closing_chicago_gives_evidence_and_what_is_missing(model, question):
    a = agent.answer_question(question, model)
    assert a['tool_log'] or 'Revenue trends alone' in a['findings']
    for need in ('operating costs', 'profitability', 'lease', 'customer behavior'):
        assert need in a['interpretation']
    assert a['next_steps'] == 'No recommendation is supported by this data.'


def test_orlando_covers_both_stores(model):
    args = agent.rules_router('What was revenue in Orlando in 2027?', model)[2]
    assert args['filters'][C.STORE] == ['SH01 Orlando, FL', 'SH08 Orlando, FL']
    a = agent.answer_question('What was revenue in Orlando in 2027?', model)
    assert 'Total in scope: $300.00' in a['findings']


def test_scope_says_full_data_or_filtered_subset_and_where_from(model):
    full = agent.answer_question('What was total revenue?', model)['scope']
    assert full.startswith('all stores, all years') and 'full data' in full
    side = agent.answer_question('What was total revenue?', model, sidebar_filters={C.YEAR: 2027})
    assert side['scope'] == '2027 (filtered subset, from the sidebar filter)'
    both = agent.answer_question('Website revenue', model, sidebar_filters={C.YEAR: 2027})['scope']
    assert 'from the sidebar filter and the question' in both
    over = agent.answer_question('Revenue in 2028', model, sidebar_filters={C.YEAR: 2027})
    assert over['tool_log'][0]['result']['value'] == 600  # the question wins, and the scope says so
    assert 'the question replaced the sidebar year filter' in over['scope']


def test_tool_crash_is_an_error_result_not_a_traceback(model):
    r = agent.run_tool('get_satisfaction_vs_revenue', {}, model, [], pd.DataFrame({C.SATISFACTION: [1.0]}))
    assert r.error and r.value is None


# ---------------------------------------- audit: Gemini path with a fake client
class FakeCall:
    def __init__(self, name, args):
        self.name, self.args = name, args


class FakeResp:
    def __init__(self, calls=None, text=''):
        self.function_calls, self.text = calls, text
        self.candidates = [type('C', (), {'content': None})()]


def fake_gemini(monkeypatch, replies):
    """Stand-in for google.genai.Client: replays canned replies, no network."""
    from google import genai
    models = type('M', (), {'generate_content': lambda self, **kw: replies.pop(0)})()
    monkeypatch.setattr(genai, 'Client', lambda api_key: type('G', (), {'models': models})())


def test_gemini_filters_merge_with_sidebar_and_scope_is_shown(model, monkeypatch):
    fake_gemini(monkeypatch, [
        FakeResp([FakeCall('get_total_revenue', {'filters': {C.CHANNEL: 'Website'}})]),
        FakeResp(text='**Findings:** 100.\n**Interpretation:** Revenue only.\n**Next steps:** None.')])
    a = agent.answer_question('Website revenue?', model, mode='llm', api_key='fake',
                              sidebar_filters={C.YEAR: 2027})
    assert a['mode'].startswith('Language model') and a['tool_log'][0]['result']['value'] == 100
    assert a['scope'] == '2027, Website (filtered subset, from the sidebar filter and the question)'
    assert a['note'] == ''


def test_gemini_cannot_call_a_function_outside_the_list(model, monkeypatch):
    fake_gemini(monkeypatch, [FakeResp([FakeCall('run_python', {'code': 'x'})]),
                              FakeResp(text='I could not do that.')])
    a = agent.answer_question('Run this', model, mode='llm', api_key='fake')
    assert 'Unknown tool' in a['tool_log'][0]['result']['error']
    assert '**Next steps:** No recommendation is supported by this data.' in a['findings']


def test_gemini_api_failure_falls_back_to_rules_without_the_key(model, monkeypatch):
    from google import genai

    def boom(api_key):
        raise RuntimeError(f'429 quota for {api_key}')
    monkeypatch.setattr(genai, 'Client', boom)
    a = agent.answer_question('What was total revenue?', model, mode='llm', api_key='SECRET')
    assert a['mode'] == 'Rules-based' and 'RuntimeError' in a['note'] and 'SECRET' not in str(a)


def test_number_not_in_a_tool_result_is_flagged(model):
    log = [{'tool': 't', 'arguments': {}, 'result': {'value': 6339640.0, 'share': 64.54}}]
    text = 'Revenue was $6,339,640, a 64.5% share, up 3 points, or $9,999,999.'
    assert agent.untraced_numbers(text, log) == ['9,999,999']


# ---------------------------------------- audit: the app itself on messy data
def run_app(tmp_path, change=None):
    """Runs the real page on a copy of data/, so nothing in data/ is touched."""
    import shutil
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    root = Path(__file__).parent.parent
    shutil.copytree(root / 'data', tmp_path / 'data')
    shutil.copy(root / 'streamlit_app.py', tmp_path / 'streamlit_app.py')
    if change:
        change(tmp_path / 'data' / 'Sales.csv')
    return AppTest.from_file(str(tmp_path / 'streamlit_app.py'), default_timeout=60).run()


def test_app_limit_message_shows_and_input_locks(tmp_path):
    at = run_app(tmp_path)
    at.radio[0].set_value(at.radio[0].options[3]).run()
    for _ in range(15):
        at.chat_input[0].set_value('What was total revenue?').run()
    assert not at.exception
    assert any('all 15 questions' in w.value for w in at.warning)
    assert at.chat_input[0].disabled


def test_app_shows_plain_message_for_missing_column(tmp_path):
    def drop(path):
        pd.read_csv(path).drop(columns=['Date']).to_csv(path, index=False)
    at = run_app(tmp_path, drop)
    assert not at.exception
    assert any("'Date'" in w.value for w in at.warning)


def test_app_partial_year_has_no_nan_on_validation_page(tmp_path):
    def add(path):
        s = pd.read_csv(path)
        jan = s[s['Date'].str.startswith('2029-01')].assign(Date='2030-01-31')
        pd.concat([s, jan]).to_csv(path, index=False)
    at = run_app(tmp_path, add)
    at.radio[0].set_value(at.radio[0].options[2]).run()
    assert not at.exception and 'nan' not in ' '.join(m.value for m in at.markdown)


def test_excel_csv_utf8_marker_does_not_hide_the_first_column():
    table = analytics.load_table(b'\xef\xbb\xbfSales ID,Revenue\nS1,5\n', 'Sales.csv')
    assert list(table.columns) == ['Sales ID', 'Revenue']
