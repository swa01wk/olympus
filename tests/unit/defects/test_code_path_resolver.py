from core.intelligence.impact.code_path import CodePathResolver


def test_code_path_ordering() -> None:
    resolver = CodePathResolver()
    candidates = resolver.resolve(
        entry_route_key="ROUTE:PATCH /tickets/{ticket_id}",
        traceback_stable_keys=["FUNC:TicketService.update_status"],
        executed_stable_keys=["ROUTE:PATCH /tickets/{ticket_id}"],
        graph_reachable=["ORM:Ticket"],
    )
    bases = [c.evidence_basis for c in candidates]
    assert bases[0] == "TRACEBACK"
    assert "GRAPH_ONLY" in bases
