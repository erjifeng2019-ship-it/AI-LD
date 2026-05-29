from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

from ai_chain_radar.db.repository import Repository

_DEFAULT_SEVERITY_PENALTY: dict[str, float] = {
    "low": 1.5,
    "medium": 3.0,
    "high": 5.0,
    "critical": 8.0,
}


@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    rule_name: str
    severity: str
    description: str
    condition_expr: str
    penalty: float

    @property
    def label(self) -> str:
        desc = self.description.strip()
        if desc:
            return f"{self.rule_name}: {desc}"
        return self.rule_name


@dataclass(frozen=True)
class RuleEvalResult:
    hits: list[RuleHit]
    total_penalty: float

    @property
    def labels(self) -> list[str]:
        return [hit.label for hit in self.hits]


class CounterEvidenceRuleEngine:
    def __init__(self, severity_penalty: dict[str, float] | None = None) -> None:
        self.severity_penalty = severity_penalty or _DEFAULT_SEVERITY_PENALTY

    def evaluate(
        self,
        repo: Repository,
        segment: str,
        metrics: dict[str, float],
    ) -> RuleEvalResult:
        rules_df = repo.query_dataframe(
            """
            SELECT
              rule_id,
              coalesce(rule_name, rule_id) AS rule_name,
              lower(coalesce(severity, 'medium')) AS severity,
              coalesce(description, '') AS description,
              coalesce(condition_expr, '') AS condition_expr
            FROM counter_evidence_rule
            WHERE coalesce(enabled, TRUE) = TRUE
              AND (segment IS NULL OR trim(segment) = '' OR segment = ?)
            ORDER BY rule_id
            """,
            [segment],
        )
        if rules_df.empty:
            return RuleEvalResult(hits=[], total_penalty=0.0)

        hits: list[RuleHit] = []
        for row in rules_df.itertuples(index=False):
            expr = str(row.condition_expr).strip()
            if not expr:
                continue
            if not _safe_eval(expr, metrics):
                continue
            severity = str(row.severity).strip() or "medium"
            penalty = float(self.severity_penalty.get(severity, self.severity_penalty["medium"]))
            hits.append(
                RuleHit(
                    rule_id=str(row.rule_id),
                    rule_name=str(row.rule_name),
                    severity=severity,
                    description=str(row.description),
                    condition_expr=expr,
                    penalty=penalty,
                )
            )

        total_penalty = min(30.0, sum(item.penalty for item in hits))
        return RuleEvalResult(hits=hits, total_penalty=total_penalty)


def _safe_eval(expr: str, variables: dict[str, float]) -> bool:
    try:
        node = ast.parse(expr, mode="eval")
        value = _eval_node(node.body, variables)
        return bool(value)
    except Exception:
        return False


def _eval_node(node: ast.AST, variables: dict[str, float]) -> Any:
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(item, variables) for item in node.values]
        if isinstance(node.op, ast.And):
            return all(bool(v) for v in values)
        if isinstance(node.op, ast.Or):
            return any(bool(v) for v in values)
        raise ValueError("Unsupported boolean operator")

    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, variables)
        if isinstance(node.op, ast.Not):
            return not bool(operand)
        if isinstance(node.op, ast.USub):
            return -float(operand)
        raise ValueError("Unsupported unary operator")

    if isinstance(node, ast.BinOp):
        left = float(_eval_node(node.left, variables))
        right = float(_eval_node(node.right, variables))
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right if right != 0 else 0.0
        if isinstance(node.op, ast.Mod):
            return left % right if right != 0 else 0.0
        raise ValueError("Unsupported binary operator")

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, variables)
        current = left
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            right = _eval_node(comparator, variables)
            if isinstance(op, ast.Gt):
                ok = float(current) > float(right)
            elif isinstance(op, ast.GtE):
                ok = float(current) >= float(right)
            elif isinstance(op, ast.Lt):
                ok = float(current) < float(right)
            elif isinstance(op, ast.LtE):
                ok = float(current) <= float(right)
            elif isinstance(op, ast.Eq):
                ok = current == right
            elif isinstance(op, ast.NotEq):
                ok = current != right
            else:
                raise ValueError("Unsupported comparison operator")
            if not ok:
                return False
            current = right
        return True

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Unsupported call")
        func_name = node.func.id
        args = [_eval_node(arg, variables) for arg in node.args]
        if func_name == "abs" and len(args) == 1:
            return abs(float(args[0]))
        if func_name == "min" and args:
            return min(float(arg) for arg in args)
        if func_name == "max" and args:
            return max(float(arg) for arg in args)
        raise ValueError("Unsupported function")

    if isinstance(node, ast.Name):
        return float(variables.get(node.id, 0.0))

    if isinstance(node, ast.Constant):
        return node.value

    raise ValueError("Unsupported AST node")
