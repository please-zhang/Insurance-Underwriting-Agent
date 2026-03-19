"""Generate synthetic underwriting applications for demos and performance tests."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from faker import Faker


PRODUCT_CODE = "LIFE-TERM-20"
PREMIUM_FREQUENCY = "annual"


def generate_applications(count: int = 100, seed: int = 42) -> list[dict]:
    faker = Faker("zh_CN")
    Faker.seed(seed)
    rng = random.Random(seed)
    applications = []

    for index in range(1, count + 1):
        age = rng.randint(18, 75)
        smoking = rng.random() < 0.25
        bmi = round(rng.uniform(18.0, 33.0), 1)
        gender = rng.choice(["male", "female"])
        health_conditions = _generate_health_conditions(age=age, rng=rng)

        applications.append(
            {
                "application_id": f"APP-SYN-{index:04d}",
                "applicant": {
                    "age": age,
                    "gender": gender,
                    "occupation": rng.choice(
                        ["office_worker", "teacher", "engineer", "sales", "retired"]
                    ),
                    "smoking": smoking,
                    "bmi": bmi,
                },
                "health_conditions": health_conditions,
                "coverage": {
                    "product_code": PRODUCT_CODE,
                    "coverage_amount": rng.choice([100000, 200000, 300000, 500000, 800000]),
                    "coverage_period_years": rng.choice([10, 15, 20, 30]),
                    "premium_frequency": PREMIUM_FREQUENCY,
                },
                "beneficiaries": [
                    {
                        "relationship": rng.choice(["spouse", "child", "parent"]),
                        "percentage": 100,
                    }
                ],
                "synthetic_profile": {
                    "name": faker.name(),
                    "city": faker.city(),
                },
            }
        )

    return applications


def write_jsonl(applications: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for application in applications:
            handle.write(json.dumps(application, ensure_ascii=False) + "\n")


def _generate_health_conditions(age: int, rng: random.Random) -> list[dict]:
    conditions: list[dict] = []

    if age >= 40 and rng.random() < 0.35:
        conditions.append(
            {
                "condition": "hypertension",
                "diagnosed_year": rng.randint(2010, 2024),
                "controlled": rng.random() < 0.7,
                "medication": rng.choice(["amlodipine", "valsartan", "none"]),
            }
        )

    if age >= 55 and rng.random() < 0.2:
        conditions.append(
            {
                "condition": "diabetes",
                "diagnosed_year": rng.randint(2005, 2024),
                "controlled": rng.random() < 0.5,
                "medication": rng.choice(["metformin", "insulin", "none"]),
            }
        )

    return conditions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成仿真投保申请数据。")
    parser.add_argument("--count", type=int, default=100, help="生成条数，默认 100。")
    parser.add_argument(
        "--output",
        default="data/synthetic/generated_applications.jsonl",
        help="输出 JSONL 文件路径。",
    )
    parser.add_argument("--seed", type=int, default=42, help="随机种子。")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    applications = generate_applications(count=args.count, seed=args.seed)
    write_jsonl(applications, Path(args.output))
    print(f"Generated {len(applications)} synthetic applications -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
