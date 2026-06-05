#pragma once

#include <cstdint>
#include <string>

#include <logos_json.h>            // LogosMap (QVariantMap on the wire)
#include <logos_module_context.h>  // LogosModuleContext base class

// A core module that depends on calc_module. It does no arithmetic of
// its own — it *composes* calc_module's primitives and showcases what
// the SDK's LogosModuleContext base class gives a universal module:
//
//   • modulePath()              — where the plugin was loaded from
//   • instanceId()              — host-assigned, stable per persistence dir
//   • instancePersistencePath() — per-instance writable data directory
//   • onContextReady()          — one-time setup hook
//   • modules()                 — typed access to declared dependencies
//                                 (sync callers, async callers, events)
//
// Because metadata.json sets "interface": "universal", the builder
// generates the Qt plugin wrapper from this plain class.
class CalcAggregatorImpl : public LogosModuleContext {
public:
    CalcAggregatorImpl() = default;
    ~CalcAggregatorImpl() = default;

    // ── The three host-injected context properties ─────────────────

    /// Directory the plugin file was loaded from (modulePath()).
    std::string moduleDir() const;

    /// Host-assigned instance ID (instanceId()).
    std::string instanceID() const;

    /// True iff the host populated a non-empty instance ID. A bool
    /// return distinguishes "host wired it" from the empty-string
    /// default a plain string getter can't tell apart over the CLI.
    bool hasInstanceID() const;

    /// Per-instance writable data directory (instancePersistencePath()).
    std::string persistenceDir() const;

    /// Increments a counter stored under persistenceDir() and returns
    /// the new value. The persistence dir is host-owned and durable, so
    /// the count keeps climbing across restarts — it is loaded back in
    /// onContextReady().
    int64_t bumpRunCount();

    // ── Compose calc_module: five sync calls into one result ───────

    /// Runs add / multiply / factorial / fibonacci / libVersion on
    /// calc_module and returns them as a single map. One call here
    /// fans out to five typed, synchronous cross-module calls.
    LogosMap computeReport(int64_t a, int64_t b, int64_t n);

    // ── Compose calc_module: an async call ─────────────────────────

    /// Fires calc_module.fibonacci(n) *asynchronously* and returns
    /// right away ("queued"). The reply lands later in a callback that
    /// stashes it; read it back with asyncResult().
    std::string startAsyncFibonacci(int64_t n);

    /// The most recent value delivered by startAsyncFibonacci()'s
    /// callback, or -1 if none has arrived yet.
    int64_t asyncResult() const;

    // ── Subscribe to a calc_module event ───────────────────────────

    /// Subscribes to calc_module's `versionReady` event with a typed
    /// callback. Returns "ok" once registered. Trigger it by calling
    /// calc_module.libVersionNotify().
    std::string subscribeVersion();

    /// The last version string delivered by the versionReady
    /// subscription, or empty until one fires.
    std::string lastVersionEvent() const;

protected:
    // One-time hook the framework fires once the context getters above
    // are populated, before any method dispatch — the canonical place
    // for setup that needs the persistence path.
    void onContextReady() override;

private:
    int64_t     m_runCount = 0;
    int64_t     m_asyncResult = -1;
    std::string m_lastVersionEvent;
    bool        m_subscribed = false;
};
