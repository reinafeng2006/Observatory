import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_architecture_documents_and_schemas_exist():
    documents = {"product_charter.md", "architecture.md", "data_provenance.md", "machine_observation.md", "company_state.md", "company_state_phase1_source_contract.md", "human_observation.md", "hypothesis_export.md"}
    assert documents <= {path.name for path in (ROOT / "docs").glob("*.md")}
    schemas = {"company_state.schema.json", "event_context.schema.json", "machine_observation.schema.json", "human_observation.schema.json", "hypothesis_package.schema.json"}
    assert schemas <= {path.name for path in (ROOT / "schemas").glob("*.json")}
    for path in (ROOT / "schemas").glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))


def test_no_strategy_validation_or_pair_scoring_module_exists():
    prohibited_stems = {"backtest", "backtesting", "strategy", "optimizer", "optimization", "pair_score", "pair_ranking", "signals", "alpha_validation"}
    module_stems = {path.stem.lower() for path in (ROOT / "observatory").rglob("*.py")}
    assert prohibited_stems.isdisjoint(module_stems)


def test_readme_states_discovery_boundary_and_product_principle():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "maximize observability, not conclusions" in readme
    assert "Observatory stops at hypothesis discovery" in readme
    assert "Machine Measurement != Human Observation" in readme
