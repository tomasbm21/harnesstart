export type Presence = "set" | "missing"

export type Check = {
  id: string
  ok: boolean
  warning: boolean
  detail: string
}

export type Backend = {
  id: string
  live_start: string
  present: boolean
  selected: boolean
}

export type StatusSnapshot = {
  source: "fixture" | "local"
  ok: boolean
  host: string
  provider: string
  model: string
  adapter: string
  keys: Record<string, Presence>
  checks: Check[]
  stubbed: string[]
  vm: {
    selected: string
    selected_source: string
    accel: string
    r2_vm_boundary: boolean
    r2_hardware_kvm: boolean
    backends: Backend[]
  }
  brains: { id: string; selected: boolean }[]
  browser: {
    observe_needs_key: boolean
    guards_need_key: boolean
    choose_needs_key: boolean
    browse_needs_key: boolean
  }
  boot: {
    notes: string[]
  }
}

const KEY_NAMES = [
  "DEEPSEEK_API_KEY",
  "TYPESAFE_API_KEY",
  "TEXT_MODEL_API_KEY",
  "WEB_API_KEY",
  "GH_TOKEN",
] as const

export const KEY_NOTES: Record<string, string> = {
  DEEPSEEK_API_KEY: "TTY doctor prompts; run needs it",
  TYPESAFE_API_KEY: "choose and browse only",
  TEXT_MODEL_API_KEY: "optional text model",
  WEB_API_KEY: "scout web backend",
  GH_TOKEN: "scout GitHub token",
}

const FALLBACK_BACKENDS = [
  "qemu",
  "firecracker",
  "celesto",
  "e2b",
  "agentenv",
  "microsandbox",
  "libkrun",
]

const FALLBACK_BRAINS = ["prime", "openhands", "openclaw", "goose"]

function presence(value: unknown): Presence {
  return value === "set" ? "set" : "missing"
}

function text(value: unknown, fallback: string): string {
  if (typeof value !== "string") return fallback
  const clipped = value.replace(/\s+/g, " ").trim().slice(0, 240)
  return clipped || fallback
}

export function normalizeStatus(raw: unknown): StatusSnapshot {
  const data = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {}
  const keysIn =
    data.keys && typeof data.keys === "object"
      ? (data.keys as Record<string, unknown>)
      : {}
  const keys: Record<string, Presence> = {}
  for (const name of KEY_NAMES) {
    keys[name] = presence(keysIn[name])
  }

  const checksIn = Array.isArray(data.checks) ? data.checks : []
  const checks: Check[] = checksIn
    .filter((item): item is Record<string, unknown> => !!item && typeof item === "object")
    .map((item) => ({
      id: text(item.id, "check"),
      ok: item.ok === true,
      warning: item.warning === true,
      detail: text(item.detail, ""),
    }))

  const vmIn =
    data.vm && typeof data.vm === "object" ? (data.vm as Record<string, unknown>) : {}
  const backendsIn = Array.isArray(vmIn.backends) ? vmIn.backends : []
  let backends: Backend[] = backendsIn
    .filter((item): item is Record<string, unknown> => !!item && typeof item === "object")
    .map((item) => ({
      id: text(item.id, ""),
      live_start: text(item.live_start, "unknown"),
      present: item.present === true,
      selected: item.selected === true,
    }))
    .filter((item) => item.id.length > 0)
  if (backends.length === 0) {
    backends = FALLBACK_BACKENDS.map((id) => ({
      id,
      live_start: id === "qemu" ? "default" : "skipped",
      present: id === "qemu",
      selected: id === "qemu",
    }))
  }

  const brainsIn = Array.isArray(data.brains) ? data.brains : []
  let brains = brainsIn
    .filter((item): item is Record<string, unknown> => !!item && typeof item === "object")
    .map((item) => ({
      id: text(item.id, ""),
      selected: item.selected === true,
    }))
    .filter((item) => item.id.length > 0)
  if (brains.length === 0) {
    brains = FALLBACK_BRAINS.map((id) => ({ id, selected: id === "prime" }))
  }

  const browserIn =
    data.browser && typeof data.browser === "object"
      ? (data.browser as Record<string, unknown>)
      : {}

  const source = data.source === "local" ? "local" : "fixture"

  return {
    source,
    ok: data.ok === true,
    host: text(data.host, "linux"),
    provider: text(data.provider, "deepseek"),
    model: text(data.model, "deepseek-v4-pro"),
    adapter: text(data.adapter, "claw-jev"),
    keys,
    checks,
    stubbed: Array.isArray(data.stubbed)
      ? data.stubbed.filter((item): item is string => typeof item === "string").map((item) => text(item, ""))
      : [],
    vm: {
      selected: text(vmIn.selected, "qemu"),
      selected_source: text(vmIn.selected_source, "default"),
      accel: text(vmIn.accel, "tcg"),
      r2_vm_boundary: vmIn.r2_vm_boundary === true,
      r2_hardware_kvm: vmIn.r2_hardware_kvm === true,
      backends,
    },
    brains,
    browser: {
      observe_needs_key: browserIn.observe_needs_key === true,
      guards_need_key: browserIn.guards_need_key === true,
      choose_needs_key: browserIn.choose_needs_key !== false,
      browse_needs_key: browserIn.browse_needs_key !== false,
    },
    boot: {
      notes: Array.isArray(data.boot && (data.boot as Record<string, unknown>).notes)
        ? ((data.boot as Record<string, unknown>).notes as unknown[])
            .filter((item): item is string => typeof item === "string")
            .map((item) => text(item, ""))
            .filter((item) => item.length > 0)
        : [],
    },
  }
}

export async function loadStatus(): Promise<StatusSnapshot> {
  for (const url of ["/status.local.json", "/status.json"]) {
    try {
      const response = await fetch(url, { cache: "no-store" })
      if (!response.ok) continue
      return normalizeStatus(await response.json())
    } catch {
      continue
    }
  }
  return normalizeStatus({
    source: "fixture",
    ok: false,
    host: "linux",
    adapter: "claw-jev",
    keys: {},
    checks: [],
    stubbed: ["desktop-watch-takeover"],
    vm: { selected: "qemu" },
    brains: [],
    browser: {},
  })
}
