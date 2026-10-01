import { shaFor } from "../engine/deterministic-id";

export const SHAS = {
  gfInit: shaFor("gf-init-001"),
  r1Integrated: shaFor("73fb91d"),
  dc003Base: shaFor("73fb91d"),
  r2Integrated: shaFor("r2-def456"),
  ic004Integrated: shaFor("982af11"),
  r3Integrated: shaFor("r3-a41c9e0"),
  candidate551: shaFor("aaa5511"),
  candidate552: shaFor("bbb5522"),
  candidate553: shaFor("ccc5533"),
  candidate554: shaFor("ddd5544"),
  candidate301: shaFor("5e1f0aa"),
  candidate603: shaFor("6c2d0b7"),
  /** @deprecated use SHAS.r1Integrated */
  dc004Base: shaFor("r2-def456"),
  dc003Draft: shaFor("r2-def456"),
  dc004Integrated: shaFor("982af11"),
} as const;
