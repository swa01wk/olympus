from core.commands.catalog import export_command_catalog, list_registered_commands


def test_catalog_covers_registered_commands() -> None:
    registered = set(list_registered_commands())
    catalog = export_command_catalog()
    names = {e["command"] for e in catalog["commands"]}
    assert registered.issubset(names)
    assert catalog["registered_count"] == len(registered)
