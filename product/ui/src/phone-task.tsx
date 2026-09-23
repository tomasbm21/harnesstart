import { useState } from "react"

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
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

const IRREVERSIBLE = /\b(pay|delete|send|post|sign up|signup)\b/i

type Props = {
  onLog: (kind: string, line: string) => void
}

export function PhoneTaskForm({ onLog }: Props) {
  const [task, setTask] = useState("")
  const [status, setStatus] = useState("Ready")
  const [diff, setDiff] = useState("No diff yet.")
  const [ask, setAsk] = useState(false)

  function queue(approved: boolean) {
    const text = task.trim()
    if (!text) return
    if (IRREVERSIBLE.test(text) && !approved) {
      setAsk(true)
      setStatus("Needs approval")
      return
    }
    setStatus("Queued on this phone")
    setDiff(`--- task\n+++ crew\n${text}\n`)
    onLog("crew", "queued on this phone (no model call)")
  }

  return (
    <Card data-testid="phone-task" className="mx-auto w-full max-w-md">
      <CardHeader>
        <CardTitle>Phone task</CardTitle>
        <p className="text-sm text-muted-foreground">
          Type a task. The crew fills the repo. This form does not call a model.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-col gap-2">
          <Label htmlFor="phone-task-text">Task</Label>
          <Textarea
            id="phone-task-text"
            data-testid="phone-task-text"
            value={task}
            onChange={(event) => setTask(event.target.value)}
            placeholder="Add a phone-width form"
            rows={4}
          />
        </div>
        <div className="flex items-center justify-between gap-2">
          <Label>Status</Label>
          <Badge data-testid="phone-task-status" variant="outline">
            {status}
          </Badge>
        </div>
        <div className="flex flex-col gap-2">
          <Label>Diff</Label>
          <pre
            data-testid="phone-task-diff"
            className="max-h-40 overflow-auto rounded-md bg-muted p-3 text-xs whitespace-pre-wrap"
          >
            {diff}
          </pre>
        </div>
      </CardContent>
      <CardFooter>
        <Button type="button" data-testid="phone-task-send" onClick={() => queue(false)}>
          Send task
        </Button>
      </CardFooter>
      <AlertDialog open={ask} onOpenChange={setAsk}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Approve this task?</AlertDialogTitle>
            <AlertDialogDescription>
              It looks irreversible. Nothing is sent until you approve it here.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel type="button">Not now</AlertDialogCancel>
            <AlertDialogAction
              type="button"
              data-testid="phone-task-approve"
              onClick={() => queue(true)}
            >
              Approve
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  )
}
