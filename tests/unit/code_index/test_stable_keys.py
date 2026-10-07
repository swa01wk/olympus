from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.stable_keys import entity_stable_key


def test_route_and_table_keys() -> None:
    assert (
        entity_stable_key(
            EntityType.ROUTE,
            file_path="app/x.py",
            qualified_name="q",
            route_method="post",
            route_path="/tickets",
        )
        == "ROUTE:POST /tickets"
    )
    assert (
        entity_stable_key(
            EntityType.TABLE,
            file_path=None,
            qualified_name="tickets",
            table_name="tickets",
        )
        == "TABLE:tickets"
    )
