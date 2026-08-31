# Intents — a guide for app developers

> **Status: shipped in Logos Basecamp.** The QML surface described here is frozen — `logos.request`,
> `logos.respond`, `intentRequested`, the six error codes and the payload rules will not change.
> The shell-side machinery around it (chooser, install suggestions) is
> deliberately replaceable and will.
>
> Nothing is signed yet, so a provider's name and label are claims rather than identity. See
> "Known limitations" in `logos-basecamp/docs/app-to-app-intents.md` before depending on this.

Intents let one app ask another to do something, **without knowing which app will answer**.
Chat doesn't know what a wallet is; it asks for "send funds" and the shell finds who can.

Applies to `ui_qml` apps. Core modules cannot participate in V1.

---

## Using a capability

**1. Declare it** in `metadata.json`:

```json
"uses": [ { "intent": "wallet.send", "cardinality": "single" } ]
```

**2. Call it** from QML:

```qml
logos.request("wallet.send",
    { chain_id: 1, to: address, amount_wei: "1000000000000000000" },
    function (res) {
        if (res.ok) showReceipt(res.data.tx_hash)
        else        showError(res.error)
    })
```

That's it. You never name an app, and you never learn which one answered.

---

## Providing a capability

**1. Declare it** in `metadata.json`:

```json
"provides": [ { "intent": "wallet.send" } ]
```

**2. Handle it** in QML:

```qml
Connections {
    target: logos
    function onIntentRequested(requestId, intent, params, requesterName) {
        if (intent !== "wallet.send") return

        confirmSheet.open(params, function (approved, txHash) {
            logos.respond(requestId, approved,
                          { tx_hash: txHash },
                          approved ? "" : "cancelled")
        })
    }
}
```

Your app is brought to the foreground automatically. Show the request, let the user decide, respond.

**3. Optionally, say what you expect.** This is how a caller finds out how to
call you — and the shell enforces it, so a payload you declared unusable never
reaches your handler:

```json
"provides": [ {
    "intent": "wallet.send",
    "params": [
        { "name": "to",     "type": "string", "required": true },
        { "name": "amount", "type": "number", "required": true },
        { "name": "memo",   "type": "string", "required": false }
    ]
} ]
```

`type` is `string` · `number` · `bool` · `object` · `array`. A missing required
field or a wrong type is refused with `bad_request` before dispatch. Fields you
did not describe are passed through untouched, so adding one later does not
break existing callers. No `params` at all means "undescribed" — not "takes
nothing" — and nothing is checked.

**4. Say whether servicing it ends**, if it doesn't.

When you respond, the shell takes the user back to whoever asked. That's right
for a transaction — they came to sign something, it's signed, they're done with
you. It's wrong when the whole point of the request was to *bring them to you*:
opening a note, landing on a page, starting something they'll want to watch.

Declare that and the shell leaves them where they are:

```json
"provides": [ { "intent": "wallet.open", "handoff": true } ]
```

Default is `false`. This controls **navigation only** — when you respond is a
separate choice, and both are normal:

- **Respond on arrival** when there is nothing to finish: you opened a page, and
  that was the whole request.
- **Hold it open** and respond when the user marks the action done. They still
  aren't sent back — you just told the caller it really happened.

Two things to get right:

- **Mind the 10-minute deadline** if you hold a request open. After that the
  shell reports `timeout` to the caller. Plenty for a button press; not for work
  waiting on a network or a chain — respond once it's *started*, and let the
  caller read the outcome from its own data source.
- **`"handoff": "true"` is a string**, not a boolean, and is refused. You'd get
  a transaction and a line in the shell's diagnostics.

---

## The result

Always three keys, always all three present:

```js
{ ok: true,  data: <anything>, error: ""        }
{ ok: false, data: undefined,  error: "<code>"  }
```

| Code | Means |
|---|---|
| `not_declared` | you forgot `uses` |
| `unavailable` | no provider, or you weren't allowed — **deliberately indistinguishable** |
| `bad_request` | your `params` were rejected — retrying unchanged won't help |
| `cancelled` | the user backed out |
| `timeout` | the provider never answered |
| `failed` | the provider reported a failure |

`bad_request` vs `failed` is the difference between "you sent the wrong thing"
and "the world didn't cooperate". Only the first is worth fixing on your side —
look at the provider's `provides[].params` to see the shape it wants.

Both the shell and the provider can send `bad_request`, and you can't tell which
did. The shell sends it when your `params` can't cross an app boundary at all
(nested past 8 levels, a string over 64 KB, a function, a QML object). A
provider sends it when the values are the wrong values. Making the two look
identical is on purpose: if shell-rejections came back instantly, the delay
alone would tell you whether a provider exists.

---

## Naming

```
namespace.verb          e.g.  wallet.send · packages.show · sign.transaction
```

Two to four dot-separated segments. Lowercase letters, digits and `_` only; each segment starts
with a letter. 3–64 characters. **`logos.*` is reserved** for the shell.

Names are matched byte-exactly. Agree on one before you ship it — a name is a contract.

---

## Six things that will trip you up

1. **`request()` returns nothing.** You get the result in the callback, never a handle to the
   provider. This is deliberate — it's what keeps your app working when the platform changes underneath.

2. **The callback always fires asynchronously**, even on immediate failure. Never assume it has
   already run by the next line.

3. **`params` and `res.data` are real JS objects**, not JSON strings. `res.data.tx_hash` works;
   don't `JSON.parse` it.

   One exception worth knowing: **arrays arrive array-*like*, not as native `Array`s.** A list that
   crosses an app boundary comes through as a Qt sequence — `length`, indexing, `map`, `forEach` and
   `JSON.stringify` all behave exactly as you expect, but **`Array.isArray()` returns `false`**, for
   every array and not just empty ones. Use the operations, not the type check; `Array.from(x)` gives
   you a real array if you need one.

4. **Send canonical data, never display strings.** Send `amount_wei`, not `"0.5 ETH"`. The provider
   re-derives what the user sees from the bytes it will act on — if your label and your payload
   disagree, the user sees the payload.

5. **Never ask for a secret on behalf of another app.** If a passphrase is needed, the *provider*
   collects it on its own screen. Never put a passphrase in `params`.

6. **`uses` entries are objects, not strings.** `[{ "intent": "x" }]`, not `["x"]`. `cardinality`
   accepts only `"single"` today.

7. **Show the result when you get it back.** Responding hands the user back to you, and arriving
   somewhere is only *explained* by seeing what happened — render the outcome ("Payment sent") on
   the screen they land on. Without it the shell looks like it moved for no reason. This is the one
   part of the round trip the shell cannot do for you: it knows the request finished, not what
   finishing meant in your app.

---

## Not possible yet

- Core (non-UI) modules as requester or provider
- Cancelling a request once sent
- Anything with no user present — every intent assumes a screen
- Choosing a provider yourself. If several apps offer a capability, **the shell asks the user** —
  you cannot influence or see that list

---

## When several apps qualify

The shell raises a chooser. You get no say in it, and that is the point.

- The list is **drawn by the shell**, with the same names and icons as the sidebar. You cannot
  influence how a provider appears, and a provider cannot dress itself up.
- It is **sorted**, so the order is stable.
- It is raised **every time**. There is no "always use this app" yet, so do not assume a repeat
  request will run without the user seeing a dialog.
- **Dismissing gives you `cancelled`**, not `unavailable` — so you can tell "the user said no" from
  "there was nobody to ask". Treat it as a normal outcome, not an error to report.

**You get the foreground back when the provider answers** — a completed request returns the user to
you, whether the provider succeeded or the user cancelled. Show the result when they arrive
(gotcha 7); the motion only reads as a consequence if the screen explains it.

Not guaranteed, though, and your app must not break without it. The shell stays put if the user
navigated away while the provider was working, if the provider declared the intent a `handoff`, or
if the request ended any way other than the provider answering — a timeout, or the provider going
away. In all of those the result still reaches your callback exactly as normal; only the navigation
is skipped. Write your handler as if focus is a bonus.

---

## Being found before you are installed

`provides` is copied into your `.lgx` manifest at bundle time, and from there into the catalog
index. That is what lets a catalog answer "which installable package provides this?" — the shell's
own registry only sees packages already on disk.

Intent **names** only. `uses` stays in `metadata.json`, because a catalog needs to know what a
package *can do*, not what it wants to call — and so do your `params` and `handoff`, because the
shell reads both from the installed file rather than the catalog's copy. Entries are objects (`{"intent": ...}`),
and a bare string is normalised up to that form.

`provides` sits inside the manifest, which is the region a package signature covers — so once
signing exists your capability claim is attested rather than merely asserted. **Nothing is signed
today**: the published catalog carries no signatures and the shell's `trustedSigners` list is empty,
so right now the claim is exactly a loose text file that anyone can write.

**What the caller sees when you are not installed:** `unavailable`, on the usual timing floor —
the same answer as if no such package existed anywhere. The shell may separately offer the user
your package, but that offer is not part of their request and never completes it. If they install
you, they retry; your first request from them is a fresh one. An app cannot tell "not installed"
from "nothing exists", by design.

---

## Design rules behind this

Worth knowing, because they explain the constraints above:

- **You name a capability, never an app** — so installing a second wallet never means changing chat.
- **The shell draws the chooser** — a requester-drawn picker could hide a rival or fake an entry.
- **The provider owns its own UI and its own secrets** — nothing sensitive crosses between apps.
- **Errors are vague on purpose** — "no such provider" and "you were denied" must look identical.

Reference: [`logos-developer-guide.md`](logos-developer-guide.md) §8.5 for the full API surface and
the `metadata.json` field reference.
