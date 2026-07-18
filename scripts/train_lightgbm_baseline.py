"""Train and persist the chronological LightGBM goal baseline."""

from database.connection import session_scope
from prediction_model.training import LightGBMBaselineTrainer


def main() -> None:
    with session_scope() as session:
        report = LightGBMBaselineTrainer(session).train()
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
