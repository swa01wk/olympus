"""Builds the application CommandBus with all Phase 01 command handlers registered."""

from __future__ import annotations

from core.commands.bus import CommandBus
from core.commands.change_handlers import handle_intake_change_request
from core.commands.ci_handlers import handle_ingest_external_ci_result
from core.commands.defect_handlers import handle_intake_defect
from core.commands.generation_handlers import (
    handle_architecture_delta_propose,
    handle_architecture_propose,
    handle_change_interpretation_rerun,
    handle_implementation_specs_generate,
    handle_release_create,
    handle_task_plan_generate,
)
from core.commands.handlers import (
    handle_approval_decide,
    handle_create_contract_draft,
    handle_create_delivery_cycle,
    handle_create_integration_candidate,
    handle_create_project,
    handle_create_task,
    handle_delivery_cycle_transition,
    handle_issue_contract,
    handle_register_repository,
    handle_request_approval,
    handle_retry_materialization,
    handle_task_add_dependency,
    handle_task_command,
    handle_update_contract_draft,
)
from core.commands.integration_handlers import (
    handle_attach_remote,
    handle_record_repository_event,
)
from core.commands.product_handlers import (
    handle_decompose_source,
    handle_ingest_product_source,
    handle_request_scope_approval,
)


def build_command_bus() -> CommandBus:
    bus = CommandBus()
    bus.register("create_project", handle_create_project)
    bus.register("integration_candidate.create", handle_create_integration_candidate)
    bus.register("create_delivery_cycle", handle_create_delivery_cycle)
    bus.register("delivery_cycle.transition", handle_delivery_cycle_transition)
    bus.register("create_task", handle_create_task)
    bus.register("task.command", handle_task_command)
    bus.register("register_repository", handle_register_repository)
    bus.register("retry_materialization", handle_retry_materialization)
    bus.register("contract.create_draft", handle_create_contract_draft)
    bus.register("contract.update_draft", handle_update_contract_draft)
    bus.register("contract.issue", handle_issue_contract)
    bus.register("approval.request", handle_request_approval)
    bus.register("approval.decide", handle_approval_decide)
    bus.register("task.add_dependency", handle_task_add_dependency)
    bus.register("ingest_product_source", handle_ingest_product_source)
    bus.register("decompose_source", handle_decompose_source)
    bus.register("request_scope_approval", handle_request_scope_approval)
    bus.register("intake_change_request", handle_intake_change_request)
    bus.register("intake_defect", handle_intake_defect)
    bus.register("record_repository_event", handle_record_repository_event)
    bus.register("attach_remote", handle_attach_remote)
    bus.register("ingest_external_ci_result", handle_ingest_external_ci_result)
    bus.register("architecture.propose", handle_architecture_propose)
    bus.register("implementation_specs.generate", handle_implementation_specs_generate)
    bus.register("task_plan.generate", handle_task_plan_generate)
    bus.register("change_interpretation.rerun", handle_change_interpretation_rerun)
    bus.register("architecture_delta.propose", handle_architecture_delta_propose)
    bus.register("release.create", handle_release_create)
    return bus
