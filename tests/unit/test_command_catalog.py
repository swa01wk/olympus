from core.commands.catalog import export_command_catalog, list_registered_commands
from core.domain.enums import ActorRole

GENERATION_COMMANDS = frozenset(
    {
        "architecture.propose",
        "implementation_specs.generate",
        "task_plan.generate",
        "change_interpretation.rerun",
        "architecture_delta.propose",
        "release.create",
    }
)


def test_generation_commands_in_catalog() -> None:
    names = {e["command"] for e in export_command_catalog()["commands"]}
    assert GENERATION_COMMANDS.issubset(names)
    for cmd in GENERATION_COMMANDS:
        entry = next(e for e in export_command_catalog()["commands"] if e["command"] == cmd)
        assert entry["target_type"] == "delivery_cycle"
        assert ActorRole.OPERATOR.value in entry["required_roles"]


def test_catalog_covers_registered_commands() -> None:
    registered = set(list_registered_commands())
    catalog = export_command_catalog()
    names = {e["command"] for e in catalog["commands"]}
    assert registered.issubset(names)
    assert catalog["registered_count"] == len(registered)
