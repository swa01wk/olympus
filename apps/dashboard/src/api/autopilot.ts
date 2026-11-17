import { apiRequest } from "@/src/api/client";
import type {
  ActivityEvent,
  AutopilotView,
  HomeProject,
  ReviewChoice,
  ReviewItem,
  StartJourneyInput,
  StartJourneyResult,
} from "@/src/api/types/autopilot";

export function fetchHome() {
  return apiRequest<HomeProject[]>("/home");
}

export function startJourney(input: StartJourneyInput, idempotencyKey?: string) {
  return apiRequest<StartJourneyResult>("/start", {
    method: "POST",
    body: { journey: "GREENFIELD_BUILD", ...input },
    idempotencyKey,
  });
}

export function fetchAutopilot(cycleId: string) {
  return apiRequest<AutopilotView>(`/delivery-cycles/${cycleId}/autopilot`);
}

export function setAutopilot(cycleId: string, enabled: boolean) {
  return apiRequest<AutopilotView>(`/delivery-cycles/${cycleId}/autopilot`, {
    method: "PUT",
    body: { enabled },
  });
}

export function retryAutopilot(cycleId: string) {
  return apiRequest<AutopilotView>(`/delivery-cycles/${cycleId}/autopilot/retry`, {
    method: "POST",
  });
}

/** What Autopilot did, newest last (plain-language messages, no raw event names). */
export function fetchAutopilotActivity(cycleId: string, limit = 40) {
  const q = new URLSearchParams({
    event_type: "autopilot.updated",
    latest: "true",
    limit: String(limit),
  });
  return apiRequest<ActivityEvent[]>(`/delivery-cycles/${cycleId}/events?${q}`);
}

/** What onboarding learned and still needs the person's confirmation. */
export function fetchReview(cycleId: string) {
  return apiRequest<ReviewItem[]>(`/delivery-cycles/${cycleId}/autopilot/review`);
}

/** Record the person's choices; items left out take Olympus's suggestion. */
export function submitReview(cycleId: string, choices: ReviewChoice[]) {
  return apiRequest<AutopilotView>(`/delivery-cycles/${cycleId}/autopilot/review`, {
    method: "POST",
    body: { choices },
  });
}
