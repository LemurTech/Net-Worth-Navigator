import unittest

import admin_app
from src import charts, model, tables


def _minimal_single_person_config(**person_overrides):
    person = {
        "name": "Alex",
        "dob": "1975-01-01",
    }
    person.update(person_overrides)
    return {
        "scenario": {"name": "Test", "slug": "test"},
        "simulation": {"start_year": 2026, "end_year": 2060},
        "assumptions": {"stock_return": 0.07, "bond_return": 0.03, "inflation": 0.025},
        "spending": {"retirement_annual": 60000},
        "person1": person,
        "events": [],
    }


class ContributionPercentValidationTests(unittest.TestCase):
    """validate_scenario previously checked person['contribution_percent'], a
    field the engine never reads (the real field is
    retirement_contribution_percent) -- so a legitimately configured
    percent-of-gross-only person always failed validation."""

    def test_percent_of_gross_only_person_passes_income_check(self):
        config = _minimal_single_person_config(
            gross_income=120000,
            retirement_contribution_percent=0.15,
        )

        _, errors = model.validate_scenario(config)

        income_errors = [e for e in errors if "Must specify either annual_take_home" in e]
        self.assertEqual(income_errors, [])

    def test_person_with_no_income_fields_still_fails_income_check(self):
        config = _minimal_single_person_config()

        _, errors = model.validate_scenario(config)

        income_errors = [e for e in errors if "Must specify either annual_take_home" in e]
        self.assertEqual(len(income_errors), 1)


class EventEnabledDefaultTests(unittest.TestCase):
    """An event omitting `enabled` entirely was treated as disabled by the
    main projection filter, _first_retirement_year, and the chart/table
    display helpers, but as enabled by _person_event_year and the Social
    Security validation check. Every call site now defaults to True
    (opt-out semantics), matching how [[events]] is documented."""

    def test_first_retirement_year_includes_event_missing_enabled_key(self):
        config = {"events": [{"type": "Retire", "person": "person1", "year": 2040}]}

        self.assertEqual(model._first_retirement_year(config), 2040)

    def test_first_retirement_year_excludes_explicitly_disabled_event(self):
        config = {"events": [{"type": "Retire", "person": "person1", "year": 2040, "enabled": False}]}

        self.assertIsNone(model._first_retirement_year(config))

    def test_chart_first_retirement_event_includes_event_missing_enabled_key(self):
        config = {"events": [{"type": "Retire", "person": "person1", "year": 2040}]}

        event = charts._first_retirement_event(config)

        self.assertIsNotNone(event)
        self.assertEqual(event["year"], 2040)

    def test_table_enabled_metrics_count_event_missing_enabled_key(self):
        events = [{"type": "Retire", "person": "person1", "year": 2040}]

        metrics = tables._events_enabled_metrics(events)

        self.assertEqual(metrics["Enabled events"], 1)


class EducationRequiredFieldsTests(unittest.TestCase):
    """Education events are always treated as a household-wide expense by the
    model regardless of the `person` field, so the Setup Panel no longer
    collects or requires it."""

    def test_person_is_not_a_required_education_field(self):
        self.assertNotIn("person", admin_app._EVENT_REQUIRED_FIELDS["Education"])
