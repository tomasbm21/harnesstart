import { useEffect, useMemo, useState, type ReactNode } from "react"
import {
  ActivityIcon,
  BrainIcon,
  KeyRoundIcon,
  MonitorIcon,
  ScrollTextIcon,
  SearchIcon,
  ServerIcon,
} from "lucide-react"
import { toast } from "sonner"

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { AspectRatio } from "@/components/ui/aspect-ratio"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card"
import { Input } from "@/components/ui/input"
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group"
import { Label } from "@/components/ui/label"
import { Popover, PopoverContent, PopoverDescription, PopoverHeader, PopoverTitle, PopoverTrigger } from "@/components/ui/popover"
import { Progress } from "@/components/ui/progress"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { Toggle } from "@/components/ui/toggle"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useTheme } from "@/components/theme-provider"
import { KEY_NOTES, loadStatus, type Presence, type StatusSnapshot } from "@/lib/status"

const IRREVERSIBLE = /\b(pay|delete|send|post|sign up|signup)\b/i

function presenceVariant(state: Presence): "default" | "outline" {
  return state === "set" ? "default" : "outline"
}

export function Console() {
  const { setTheme, theme } = useTheme()
  const [status, setStatus] = useState<StatusSnapshot | null>(null)
  const [tab, setTab] = useState("overview")
  const [compact, setCompact] = useState(false)
  const [commandsOpen, setCommandsOpen] = useState(false)
  const [hideMissing, setHideMissing] = useState(false)
  const [keyFilter, setKeyFilter] = useState("")
  const [vm, setVm] = useState("qemu")
  const [pinQemu, setPinQemu] = useState(false)
  const [brain, setBrain] = useState("prime")
  const [url, setUrl] = useState("https://example.com")
  const [goal, setGoal] = useState("Stop when the heading is visible")
  const [timeoutSec, setTimeoutSec] = useState(8)
  const [liveOptIn, setLiveOptIn] = useState(false)
  const [logFilter, setLogFilter] = useState("all")
  const [log, setLog] = useState<string[]>([])
  const [policyOpen, setPolicyOpen] = useState(false)
  const [pending, setPending] = useState<"choose" | "browse" | null>(null)
  const [blockOpen, setBlockOpen] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    let cancelled = false
    loadStatus().then((snapshot) => {
      if (cancelled) return
      setStatus(snapshot)
      setVm(snapshot.vm.selected || "qemu")
      const selectedBrain = snapshot.brains.find((item) => item.selected)
      setBrain(selectedBrain?.id || "prime")
    })
    return () => {
      cancelled = true
    }
  }, [])

  const ready = useMemo(() => {
    if (!status) return 0
    if (status.checks.length === 0) return status.ok ? 100 : 40
    const ok = status.checks.filter((check) => check.ok).length
    return Math.round((ok / status.checks.length) * 100)
  }, [status])

  function pushLog(kind: string, line: string) {
    const stamp = new Date().toISOString().slice(11, 19)
    setLog((prev) => [`${stamp}  ${kind}  ${line}`, ...prev].slice(0, 40))
    toast.success(`${kind} logged locally`)
  }

  function runOffline(kind: "observe" | "guards") {
    const needs = kind === "observe" ? status?.browser.observe_needs_key : status?.browser.guards_need_key
    pushLog(
      kind,
      `${url || "(no url)"}  typesafe=${needs ? "required" : "not-required"}  timeout=${timeoutSec}s  mock`,
    )
  }

  function askLive(kind: "choose" | "browse") {
    if (IRREVERSIBLE.test(goal)) {
      setPending(kind)
      setBlockOpen(true)
      return
    }
    setPending(kind)
    setPolicyOpen(true)
  }

  function confirmLive() {
    if (!pending || !status) return
    const key = status.keys.TYPESAFE_API_KEY
    if (!liveOptIn) {
      pushLog(pending, "CLAW_BROWSER_LIVE is off. No TypeSafe call.")
    } else if (key !== "set") {
      pushLog(pending, "would exit 2: TYPESAFE_API_KEY missing. Value not shown.")
    } else {
      pushLog(pending, "key is set. This console still does not call TypeSafe.")
    }
    setPolicyOpen(false)
    setPending(null)
  }

  function refresh() {
    setRefreshing(true)
    window.setTimeout(() => {
      setRefreshing(false)
      pushLog("doctor", `fixture ${status?.source ?? "fixture"} re-read in the page`)
    }, 350)
  }

  const visibleKeys = Object.entries(status?.keys ?? {}).filter(([name, state]) => {
    if (hideMissing && state === "missing") return false
    if (!keyFilter.trim()) return true
    return name.toLowerCase().includes(keyFilter.trim().toLowerCase())
  })

  const visibleLog = log.filter((line) => {
    if (logFilter === "all") return true
    return line.includes(`  ${logFilter}  `)
  })

  if (!status || refreshing) {
    return (
      <main className="mx-auto flex min-h-svh max-w-6xl flex-col gap-4 p-6">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-24 w-full" />
        <div className="grid gap-3 md:grid-cols-3">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
      </main>
    )
  }

  const typesafe = status.keys.TYPESAFE_API_KEY

  return (
      <main className={`mx-auto flex min-h-svh max-w-6xl flex-col gap-4 p-4 md:p-6 ${compact ? "text-xs" : ""}`}>
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Avatar>
              <AvatarFallback>NC</AvatarFallback>
            </Avatar>
            <div>
              <Breadcrumb>
                <BreadcrumbList>
                  <BreadcrumbItem>Norfront</BreadcrumbItem>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>Claw</BreadcrumbItem>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    <BreadcrumbPage>Operator</BreadcrumbPage>
                  </BreadcrumbItem>
                </BreadcrumbList>
              </Breadcrumb>
              <h1 className="text-lg font-semibold tracking-tight">Norfront Claw</h1>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={status.ok ? "default" : "destructive"}>{status.ok ? "doctor ok" : "doctor warn"}</Badge>
            <Badge variant="outline">{status.host}</Badge>
            <Badge variant="secondary" data-testid="status-source">
              {status.source}
            </Badge>
            <HoverCard>
              <HoverCardTrigger asChild>
                <Button variant="outline" size="sm" type="button">
                  {status.adapter}
                </Button>
              </HoverCardTrigger>
              <HoverCardContent className="w-72 text-sm">
                Jev hook. Observe and guards do not need TypeSafe. Desktop watch and takeover stay stubbed.
              </HoverCardContent>
            </HoverCard>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" type="button" data-testid="session-menu">
                  Session
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Theme ({theme})</DropdownMenuLabel>
                <DropdownMenuItem onClick={() => setTheme("dark")}>Dark</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setTheme("light")}>Light</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuCheckboxItem
                  checked={compact}
                  onCheckedChange={(checked) => setCompact(checked === true)}
                >
                  Compact density
                </DropdownMenuCheckboxItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button variant="secondary" size="sm" type="button" onClick={() => setCommandsOpen(true)}>
              <SearchIcon />
              Commands
            </Button>
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline" size="sm" type="button">
                  <ScrollTextIcon />
                  Log
                </Button>
              </SheetTrigger>
              <SheetContent>
                <SheetHeader>
                  <SheetTitle>Local event log</SheetTitle>
                  <SheetDescription>Mock actions only. Nothing here calls a vendor.</SheetDescription>
                </SheetHeader>
                <ScrollArea className="h-[70vh] px-4">
                  <LogList lines={log} empty="No events yet." />
                </ScrollArea>
              </SheetContent>
            </Sheet>
          </div>
        </header>

        <Alert>
          <ActivityIcon />
          <AlertTitle>Local operator console</AlertTitle>
          <AlertDescription>
            Keys render as set or missing. This page does not read secret values and does not call DeepSeek or TypeSafe.
          </AlertDescription>
        </Alert>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="doctor">Doctor</TabsTrigger>
            <TabsTrigger value="keys">Keys</TabsTrigger>
            <TabsTrigger value="computer">Computer</TabsTrigger>
            <TabsTrigger value="browser">Browser</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="flex flex-col gap-4">
            <div className="grid gap-3 md:grid-cols-4">
              <Metric icon={<ActivityIcon />} label="Checks" value={`${ready}%`} />
              <Metric icon={<ServerIcon />} label="VM" value={vm} />
              <Metric icon={<BrainIcon />} label="Brain" value={brain} />
              <Metric icon={<KeyRoundIcon />} label="TypeSafe" value={typesafe} />
            </div>
            <Card>
              <CardHeader>
                <CardTitle>Readiness</CardTitle>
                <CardDescription>
                  {status.provider}/{status.model} · accel {status.vm.accel} · source {status.vm.selected_source}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Progress value={ready} />
                <div className="flex flex-wrap gap-2">
                  <Badge variant={status.vm.r2_vm_boundary ? "default" : "outline"}>
                    r2 boundary {status.vm.r2_vm_boundary ? "yes" : "no"}
                  </Badge>
                  <Badge variant={status.vm.r2_hardware_kvm ? "default" : "secondary"}>
                    hardware kvm {status.vm.r2_hardware_kvm ? "yes" : "no"}
                  </Badge>
                  <Badge variant="outline">observe key {status.browser.observe_needs_key ? "yes" : "no"}</Badge>
                  <Badge variant="outline">guards key {status.browser.guards_need_key ? "yes" : "no"}</Badge>
                </div>
              </CardContent>
              <CardFooter className="gap-2">
                <Button type="button" size="sm" onClick={refresh} data-testid="refresh-status">
                  Refresh view
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={() => setTab("browser")}>
                  Open browser
                </Button>
              </CardFooter>
            </Card>
          </TabsContent>

          <TabsContent value="doctor" className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Doctor checks</CardTitle>
                <CardDescription>Same labels the CLI prints. Details stay short and secret-free.</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Check</TableHead>
                      <TableHead>State</TableHead>
                      <TableHead>Detail</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {status.checks.map((check) => (
                      <TableRow key={check.id}>
                        <TableCell className="font-medium">{check.id}</TableCell>
                        <TableCell>
                          <Badge variant={check.ok && !check.warning ? "default" : "secondary"}>
                            {check.ok ? (check.warning ? "warn" : "ok") : "fail"}
                          </Badge>
                        </TableCell>
                        <TableCell>{check.detail}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
            <Accordion type="single" collapsible>
              {status.stubbed.map((item) => (
                <AccordionItem key={item} value={item}>
                  <AccordionTrigger>{item}</AccordionTrigger>
                  <AccordionContent>
                    Still stubbed in the Linux-cloud CLI. This console does not implement it.
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </TabsContent>

          <TabsContent value="keys" className="flex flex-col gap-4">
            <div className="flex flex-wrap items-end gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="key-filter">Filter names</Label>
                <Input
                  id="key-filter"
                  value={keyFilter}
                  onChange={(event) => setKeyFilter(event.target.value)}
                  placeholder="DEEPSEEK, TYPESAFE…"
                  className="w-56"
                />
              </div>
              <Label className="mb-2 gap-2">
                <Checkbox
                  checked={hideMissing}
                  onCheckedChange={(checked) => setHideMissing(checked === true)}
                />
                Hide missing
              </Label>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Presence</TableHead>
                  <TableHead>Used for</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleKeys.map(([name, state]) => (
                  <TableRow key={name}>
                    <TableCell className="font-mono text-xs">{name}</TableCell>
                    <TableCell>
                      <Badge variant={presenceVariant(state)} data-testid={`key-${name}`}>
                        {state}
                      </Badge>
                    </TableCell>
                    <TableCell>{KEY_NOTES[name] ?? "presence only"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {visibleKeys.length === 0 ? (
              <Alert>
                <AlertTitle>No keys match</AlertTitle>
                <AlertDescription>Clear the filter or show missing names. Values are never listed.</AlertDescription>
              </Alert>
            ) : null}
          </TabsContent>

          <TabsContent value="computer" className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>VM backend</CardTitle>
                <CardDescription>
                  QEMU stays the default. Selecting here does not start a guest or probe KVM.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div className="flex items-center gap-2">
                  <Label htmlFor="vm-backend">Backend</Label>
                  <Toggle
                    pressed={pinQemu}
                    onPressedChange={setPinQemu}
                    aria-label="Pin qemu"
                    size="sm"
                  >
                    Pin qemu
                  </Toggle>
                </div>
                <Select
                  value={pinQemu ? "qemu" : vm}
                  onValueChange={setVm}
                  disabled={pinQemu}
                >
                  <SelectTrigger id="vm-backend" className="w-full" data-testid="vm-select">
                    <SelectValue placeholder="qemu" />
                  </SelectTrigger>
                  <SelectContent>
                    {status.vm.backends.map((backend) => (
                      <SelectItem key={backend.id} value={backend.id}>
                        {backend.id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-sm text-muted-foreground" data-testid="vm-current">
                  Selected {pinQemu ? "qemu" : vm}
                </p>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Id</TableHead>
                      <TableHead>Live start</TableHead>
                      <TableHead>Present</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {status.vm.backends.map((backend) => (
                      <TableRow key={backend.id}>
                        <TableCell>{backend.id}</TableCell>
                        <TableCell>{backend.live_start}</TableCell>
                        <TableCell>{backend.present ? "yes" : "no"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Brain</CardTitle>
                <CardDescription>Prime is the default. CLAW_BRAIN wins on the CLI. This control is local.</CardDescription>
              </CardHeader>
              <CardContent>
                <RadioGroup value={brain} onValueChange={setBrain} className="gap-3">
                  {status.brains.map((item) => (
                    <Label key={item.id} className="gap-2 font-normal" htmlFor={`brain-${item.id}`}>
                      <RadioGroupItem id={`brain-${item.id}`} value={item.id} />
                      {item.id}
                      {item.id === "prime" ? <Badge variant="outline">default</Badge> : null}
                    </Label>
                  ))}
                </RadioGroup>
              </CardContent>
              <CardFooter>
                <Badge data-testid="brain-current">{brain}</Badge>
              </CardFooter>
            </Card>
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Desktop watch</CardTitle>
                <CardDescription>Stubbed. The Jev inspector lives on the adapter, not this CLI.</CardDescription>
              </CardHeader>
              <CardContent>
                <AspectRatio ratio={16 / 5} className="overflow-hidden rounded-lg border bg-muted">
                  <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                    <MonitorIcon className="mr-2 size-4" />
                    takeover not wired
                  </div>
                </AspectRatio>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="browser" className="flex flex-col gap-4">
            <Alert variant={liveOptIn && typesafe !== "set" ? "destructive" : "default"}>
              <AlertTitle>{liveOptIn ? "Live opt-in is on in the page" : "Offline path"}</AlertTitle>
              <AlertDescription>
                {liveOptIn
                  ? "CLAW_BROWSER_LIVE is a local switch. Choose and browse still do not call TypeSafe from this page."
                  : "Observe and guards are the default path. They do not need TypeSafe and they do not hang CI."}
              </AlertDescription>
            </Alert>
            <div className="grid gap-4 lg:grid-cols-[1.4fr_0.8fr]">
              <Card>
                <CardHeader>
                  <CardTitle>Jev controls</CardTitle>
                  <CardDescription>Mock of ./product/claw observe, guards, choose, and browse.</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="page-url">Page URL</Label>
                    <InputGroup>
                      <InputGroupAddon>
                        <InputGroupText>URL</InputGroupText>
                      </InputGroupAddon>
                      <InputGroupInput
                        id="page-url"
                        value={url}
                        onChange={(event) => setUrl(event.target.value)}
                      />
                    </InputGroup>
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="goal">Goal</Label>
                    <Textarea id="goal" value={goal} onChange={(event) => setGoal(event.target.value)} />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label>Stub timeout {timeoutSec}s</Label>
                    <Slider
                      min={5}
                      max={30}
                      value={[timeoutSec]}
                      onValueChange={(value) => setTimeoutSec(value[0] ?? 8)}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch
                      id="live-opt-in"
                      checked={liveOptIn}
                      onCheckedChange={setLiveOptIn}
                      data-testid="live-switch"
                    />
                    <Label htmlFor="live-opt-in">CLAW_BROWSER_LIVE</Label>
                  </div>
                  <Separator />
                  <div className="flex flex-wrap gap-2">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button type="button" onClick={() => runOffline("observe")} data-testid="observe">
                          Observe
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>No TypeSafe key</TooltipContent>
                    </Tooltip>
                    <Button type="button" variant="outline" onClick={() => runOffline("guards")} data-testid="guards">
                      Guards
                    </Button>
                    <Button type="button" variant="secondary" onClick={() => askLive("choose")} data-testid="choose">
                      Choose
                    </Button>
                    <Button type="button" variant="destructive" onClick={() => askLive("browse")} data-testid="browse">
                      Browse
                    </Button>
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button type="button" variant="ghost">
                          Policy
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent>
                        <PopoverHeader>
                          <PopoverTitle>policy_status</PopoverTitle>
                          <PopoverDescription>Booleans only.</PopoverDescription>
                        </PopoverHeader>
                        <ul className="mt-2 space-y-1 text-sm">
                          <li>observe needs key: {String(status.browser.observe_needs_key)}</li>
                          <li>guards need key: {String(status.browser.guards_need_key)}</li>
                          <li>choose needs key: {String(status.browser.choose_needs_key)}</li>
                          <li>browse needs key: {String(status.browser.browse_needs_key)}</li>
                          <li>TYPESAFE_API_KEY: {typesafe}</li>
                        </ul>
                      </PopoverContent>
                    </Popover>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Event log</CardTitle>
                  <CardDescription>Local lines from the buttons above.</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <ToggleGroup
                    type="single"
                    value={logFilter}
                    onValueChange={(value) => {
                      if (value) setLogFilter(value)
                    }}
                    variant="outline"
                    size="sm"
                  >
                    <ToggleGroupItem value="all">All</ToggleGroupItem>
                    <ToggleGroupItem value="observe">Observe</ToggleGroupItem>
                    <ToggleGroupItem value="guards">Guards</ToggleGroupItem>
                    <ToggleGroupItem value="choose">Choose</ToggleGroupItem>
                  </ToggleGroup>
                  <ScrollArea className="h-56 rounded-md border">
                    <div data-testid="event-log" className="p-3">
                      <LogList lines={visibleLog} empty="Run observe or guards." />
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>
            </div>
            <Collapsible>
              <CollapsibleTrigger asChild>
                <Button type="button" variant="outline" size="sm">
                  How CI should test Jev
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2 text-sm text-muted-foreground">
                Default runs use the fake adapter for observe and guards, with a short timeout and no TypeSafe key.
                Live choose and browse stay behind CLAW_BROWSER_LIVE=1 and never prompt on a non-TTY.
              </CollapsibleContent>
            </Collapsible>
          </TabsContent>
        </Tabs>

        <CommandDialog open={commandsOpen} onOpenChange={setCommandsOpen} title="Claw commands">
          <Command>
          <CommandInput placeholder="Jump to a panel or mock a browser call" />
          <CommandList>
            <CommandEmpty>No matching command.</CommandEmpty>
            <CommandGroup heading="Panels">
              {["overview", "doctor", "keys", "computer", "browser"].map((name) => (
                <CommandItem
                  key={name}
                  onSelect={() => {
                    setTab(name)
                    setCommandsOpen(false)
                  }}
                >
                  {name}
                  <CommandShortcut>tab</CommandShortcut>
                </CommandItem>
              ))}
            </CommandGroup>
            <CommandSeparator />
            <CommandGroup heading="Browser">
              <CommandItem
                onSelect={() => {
                  setTab("browser")
                  setCommandsOpen(false)
                  runOffline("observe")
                }}
              >
                observe
              </CommandItem>
              <CommandItem
                onSelect={() => {
                  setTab("browser")
                  setCommandsOpen(false)
                  runOffline("guards")
                }}
              >
                guards
              </CommandItem>
            </CommandGroup>
          </CommandList>
          </Command>
        </CommandDialog>

        <Dialog open={policyOpen} onOpenChange={setPolicyOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{pending === "browse" ? "Browse" : "Choose"} stays local</DialogTitle>
              <DialogDescription>
                {liveOptIn
                  ? typesafe === "set"
                    ? "The key is present. This page still does not send it anywhere."
                    : "TYPESAFE_API_KEY is missing, so a real CLI choose or browse would exit 2."
                  : "CLAW_BROWSER_LIVE is off, so this stays on the offline path."}
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setPolicyOpen(false)}>
                Cancel
              </Button>
              <Button type="button" onClick={confirmLive} data-testid="confirm-live">
                Log decision
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <AlertDialog open={blockOpen} onOpenChange={setBlockOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Irreversible goal blocked</AlertDialogTitle>
              <AlertDialogDescription>
                Pay, post, delete, and sign-up wording is blocked unless CLAW_ALLOW_IRREVERSIBLE=1. This console does not set that flag.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Close</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => {
                  pushLog(pending ?? "browse", "blocked irreversible goal")
                  setPending(null)
                }}
              >
                Record block
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </main>
  )
}

function Metric({
  icon,
  label,
  value,
}: {
  icon: ReactNode
  label: string
  value: string
}) {
  return (
    <Card>
      <CardHeader>
        <CardDescription className="flex items-center gap-2">
          {icon}
          {label}
        </CardDescription>
        <CardTitle className="capitalize">{value}</CardTitle>
      </CardHeader>
    </Card>
  )
}

function LogList({ lines, empty }: { lines: string[]; empty: string }) {
  if (lines.length === 0) {
    return <p className="text-sm text-muted-foreground">{empty}</p>
  }
  return (
    <ul className="space-y-2 font-mono text-xs">
      {lines.map((line, index) => (
        <li key={`${index}-${line}`}>{line}</li>
      ))}
    </ul>
  )
}
