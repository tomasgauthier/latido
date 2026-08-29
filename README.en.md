<img src="logo.svg" width="72" align="right" alt="">

# Latido

*[Español](README.md)*

An agent that wakes up on its own, checks whether anything worth knowing has
happened, and messages you on Telegram when it has. On the vast majority of
beats it says nothing — which is the point. One that reports "all good" every
few hours gets muted within two days.

It runs on Claude Code in headless mode. **It does not depend on any open
session**: every beat is a fresh session that lives for seconds and dies, and
continuity between beats lives in a configurable memory file (the `memoria`
key in `config.json`; `estado.md` by default). Close everything and it keeps
beating.

> `prompt.md` ships in Spanish, so out of the box the agent writes to you in
> Spanish. An English version is included — `cp prompt.en.md prompt.md` and
> you're done. That file is plain text and it *is* the whole personality;
> rewrite it in any language and everything else works unchanged.

## What you need

- **macOS or Linux.** On a Mac the three agents run under `launchd`; on Linux,
  under `systemd` user units. It picks one on its own — what changes is the
  init system, not the heartbeat.
- **[Claude Code](https://claude.com/claude-code)** installed and logged in.
  Check with `claude -p "hello"`.
- **A Telegram bot.** Ask [@BotFather](https://t.me/botfather) for one with
  `/newbot`; it takes thirty seconds and hands you a token. Make it a bot
  **dedicated to the latido**: two programs polling the same message queue steal
  each other's messages.
- **Python 3.** The one macOS ships with is fine. Nothing to install.

## Install

```sh
git clone <this repo> latido && cd latido
cp config.example.json config.json && chmod 600 config.json
./servidor.py --instalar        # keeps the page alive, and starts it at login
open http://127.0.0.1:8737
```

Everything else happens on that page, in this order:

1. **Telegram** — paste the bot token and save. Then send the bot anything from
   your own Telegram and hit **Detectar**: it captures the chat by itself. Until
   that step is done, the latido accepts messages from nobody.
2. **Fuentes** (sources) — the folders that matter. An *Elegir…* button opens a
   folder browser, so you never type a path. Next to each, what it is in one
   sentence — that description is what it uses to know what to look for there.
3. **Ritmo** (pace) — how often it looks on its own. Four hours is a good
   starting point; half an hour is useful for the first day of testing.
4. **Motor** (engine) — which program wakes up on each beat. Installed ones are
   detected for you; if it's Claude Code, change nothing.
5. **Prender** (turn on).

No paths are hardcoded anywhere: the launchd agents are generated with the
location of the repo you just cloned, and the Claude Code binary is looked up in
`PATH` and the usual places. If yours lives somewhere unusual, add
`"claude": "/path/to/binary"` to `config.json`.

The server listens on `127.0.0.1` only — it edits files and loads launchd
agents, it has no business on the network.

## How it works

Three launchd agents, and the split is the whole idea: **listening is free,
thinking is what costs.**

```
  escucha.py  ── waits for a message from you (an open socket, costs nothing)
       │
       └──> latido.py <──── the clock, every N hours
                │
                └──> claude -p ──> anything to say? ──> Telegram
```

| Agent | What it is | How it stays up |
|---|---|---|
| `local.latido.escucha` | The ear. Answers you right away | `KeepAlive` — revived if it dies |
| `local.latido` | The clock. Looks on its own | `StartInterval` |
| `local.latido.web` | The config page | `KeepAlive` |

The ear is the **only** thing that reads from Telegram: two consumers of the
same queue steal each other's messages. It drops what arrives into `buzon.txt`
and the latido reads from there.

**Only messages from the configured chat get through.** Anyone who knows your
bot's `@username` can write to it, and without that filter their text would land
in the prompt of an agent that reads your files. Messages from other chats are
discarded unread and noted in the ear's log. Until you've done the **Detectar**
step, nobody gets through — not even you.

| File | What it is |
|---|---|
| `latido.py` | The beat. Reads the mail, wakes Claude, sends and logs. |
| `escucha.py` | The ear. Waits for messages and fires a beat on arrival. |
| `servidor.py` | The config page. Standard library, no dependencies. |
| `index.html` | That page. One file, no build step. |
| `prompt.md` | Its behavior: when to shut up, how to write, what to ignore. It's an example: the `prompt` key in `config.json` points it wherever you want. |
| `config.json` | Your settings and the token. Mode `600`, out of git. |

## Where the record lives

The latido writes up to two things about your life: `bitacora/`, one file per
day with what it said or why it stayed quiet, and — if you've configured a
memory — whatever file you point `memoria` to (`config.json`; `estado.md` by
default). That log is what makes the thing tunable — you read why it stayed
quiet and adjust the prompt until it speaks when it should.

Memory is optional: set it to `null` if continuity between beats already lives
somewhere else — a task system, a database — and you don't want the latido
inventing a file of its own for it. Without one, the latido reads and rewrites
nothing between beats; its only memory is the day's log.

**By default they land inside the repository, which is probably not what you
want.** Under *Registro* on the page you can point them somewhere else — an
Obsidian vault, say, where you read them like any other note. These files are
kept out of git on purpose: they're your diary, not the tool, and they have no
business travelling with the code if you ever publish this.

## Why not just a remote control?

Session remote controls exist — Claude Code's Remote Control, for one — letting
you reach a running session from your phone. They beat this at almost
everything: full power, real conversation, any repository. If you have a session
open and want to ask it something, use that.

| | A remote control | A heartbeat |
|---|---|---|
| Who starts | You, always | It does too |
| Needs a live session | Yes | No: it creates one |
| Reach | Full, conversational | One short shot, few tools |
| When nothing is open | Nothing to connect to | Still works |

The whole difference fits in the first row. **A remote control has no
initiative**: it brings you closer to your session, but it will never write to
you. This exists for the other half — for something to tell you, on a Sunday
morning with the laptop shut and nothing running, that a proposal has been
sitting untouched for nine days.

It's a narrow moat. But it's the one a remote control cannot cross.

## Talking to it

Message the bot whenever you like: the ear is awake and fires a beat the moment
your message lands. The pace only governs how often it looks **on its own
initiative**, unprompted.

It only has the tools you give it under `herramientas` in `config.json`. Out of
the box it reads files and writes; to let it use one of your MCP servers, add
that tool's name to the list.

## The model

Sonnet by default. Its job is deciding **not** to speak, and that's where small
models go to an extreme: they either speak every time or never. Haiku works if
you narrow the judgment down to something mechanical.

## So it doesn't die quietly

Silence is its normal result, which means **a broken latido looks exactly like a
quiet one**. If your Claude session expires tomorrow, you will notice nothing.

That's why it writes `.ultimo` when it finishes — **but only if it went well**.
If it measured execution instead of success, one that runs and fails every time
would look healthy. Point any freshness monitor at that file with a limit of
about three times the pace, and you'll find out.

## Without the page

```sh
./latido.py                                      # one beat now
./servidor.py --instalar                         # keep the page always alive
launchctl bootout gui/$UID/local.latido          # stop the clock
launchctl bootout gui/$UID/local.latido.escucha  # stop the ear
tail -f /tmp/local.latido.escucha.log            # what it hears
```

## Another CLI, another provider

The latido asks nothing special of anyone: it runs your provider's official CLI,
in its non-interactive mode, with your own already-authenticated session. It
does not extract credentials, forward them anywhere, stand up a proxy, drive a
user interface, or scrape anything. It is exactly what you would type in your
terminal — only a timer types it.

That's why the invocation is configurable. Any CLI that **takes a prompt as an
argument and returns text on stdout** will do:

```json
"cli": {
  "bin": "claude",
  "args": ["-p", "{prompt}", "--model", "{modelo}",
           "--permission-mode", "acceptEdits",
           "--allowedTools", "{herramientas}",
           "--output-format", "json"],
  "flag_carpeta": "--add-dir"
}
```

- `{prompt}` is replaced by the full instructions.
- `{modelo}` by whatever you pick on the page.
- `{herramientas}` expands into several arguments, one per tool.
- `--output-format json` is what lets it record what each beat cost.
  If your CLI has no such flag, drop it: it still works, just without figures.
- `flag_carpeta` is repeated once per source. Leave it empty if your CLI has no
  such concept — the model then learns the paths from the prompt and reads them
  with its own tools.

The only thing the latido needs from the other side is that the model **can
write a file**: `salida.txt` is its one and only voice.

**On terms of service:** every provider has its own and they change. This works
around nothing — it uses the official client exactly as shipped — but if you're
going to run it unattended, reading your provider's terms is on you, not on this
repository.
