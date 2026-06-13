#include "V2Record.h"
#include "CardType.h"
#include "CardBuyable.h"
#include "Resources.h"
#include <algorithm>
#include <string>
#include <vector>

#include "rapidjson/document.h"
#include "rapidjson/writer.h"
#include "rapidjson/stringbuffer.h"

namespace Prismata
{

namespace
{
    // Push a string member with a heap-allocated copy (key is a static StringRef).
    void addStr(rapidjson::Value & obj, const char * key, const std::string & s,
                rapidjson::Document::AllocatorType & a)
    {
        rapidjson::Value v(s.c_str(), static_cast<rapidjson::SizeType>(s.size()), a);
        obj.AddMember(rapidjson::StringRef(key), v, a);
    }

    // The 6 mana keys, mirroring js_engine/state_adapter.js::manaToResources.
    // Resources enum: Gold=0, Energy=1, Blue=2, Red=3, Green=4, Attack=5.
    rapidjson::Value manaToResources(const GameState & state, const PlayerID p,
                                     rapidjson::Document::AllocatorType & a)
    {
        const Resources & r = state.getResources(p);
        rapidjson::Value o(rapidjson::kObjectType);
        o.AddMember("gold",   static_cast<int>(r.amountOf(Resources::Gold)),   a);
        o.AddMember("green",  static_cast<int>(r.amountOf(Resources::Green)),  a);
        o.AddMember("blue",   static_cast<int>(r.amountOf(Resources::Blue)),   a);
        o.AddMember("red",    static_cast<int>(r.amountOf(Resources::Red)),    a);
        o.AddMember("energy", static_cast<int>(r.amountOf(Resources::Energy)), a);
        o.AddMember("attack", static_cast<int>(r.amountOf(Resources::Attack)), a);
        return o;
    }

    // One per-instance token, reproducing js_engine/state_adapter.js::instToRichUnit
    // EXACTLY. All inputs are read-only accessors used by ReplaySerializer::serializeState.
    rapidjson::Value instToRichUnit(const Card & c, rapidjson::Document::AllocatorType & a)
    {
        const CardType ct = c.getType();

        // Raw engine values (same as serializeState emits as "health"/"damage"/etc.).
        const int health     = static_cast<int>(c.currentHealth());   // JS inst.health
        const int damage     = static_cast<int>(c.getDamageTaken());  // JS inst.damage
        const int constrTime = static_cast<int>(c.getConstructionTime());
        const int delay      = static_cast<int>(c.getCurrentDelay());
        const int chill      = static_cast<int>(c.currentChill());    // JS inst.disruptDamage
        const int charge     = static_cast<int>(c.getCurrentCharges());// JS inst.charge
        // lifespan: engine convention is 0 == "no lifespan". serializeState emits that as -1.
        // The V2 field collapses "no lifespan" to 0 (matches JS: lifespan === -1 ? 0 : ...).
        const int curLife    = static_cast<int>(c.getCurrentLifespan());
        const int lifespanRem = (curLife == 0) ? 0 : std::max(0, curLife);

        const bool fragile    = ct.isFragile();
        const int  baseHealth = static_cast<int>(ct.getStartingHealth()); // JS card.startingHealth (||1 below)

        // JS: fragile ? health : (health - damage)
        const int rawHp     = fragile ? health : (health - damage);
        const int currentHp = std::max(0, rawHp);

        // role===ROLE_ASSIGNED <-> C++ CardStatus::Assigned.
        // inst.blocking (JS / SWF): the blocking-MODE flag = type-level canBlock(assigned)
        // (assigned ? assignedBlocking : defaultBlocking) AND NOT under construction AND NOT
        // FROZEN (chill >= current HP; Card::isFrozen, the engine's own rule). The old
        // "residual full-chill edge ... follow-up" here was a REAL silent feature skew (the
        // fifth of the v2.2.1 class), proven 2026-06-13 by the B3 fixtures (ke6MK-xlFvv
        // p21/p28: the faithful JS engine exports is_blocking=0 on frozen blockers while
        // both C++ legs said 1). Do NOT use the fully-gated Card::canBlock() (it also drops
        // DELAYED units; the SWF keeps delayed and PARTIALLY-chilled units blocking).
        const bool assigned = (c.getStatus() == CardStatus::Assigned);
        const bool blocking = ct.canBlock(assigned) && !c.isUnderConstruction() && !c.isFrozen();

        const bool isConstructing = (constrTime > 0);
        const int  turnsUntilReady = std::max(constrTime, delay);

        // hp_fraction = baseHealth>0 ? currentHp/baseHealth : 0 ; JS uses startingHealth||1.
        const int  baseForFraction = (baseHealth > 0) ? baseHealth : 1;
        const double hpFraction = (baseHealth > 0)
                                ? (static_cast<double>(currentHp) / static_cast<double>(baseForFraction))
                                : 0.0;

        rapidjson::Value o(rapidjson::kObjectType);
        addStr(o, "name", ct.getUIName(), a);
        o.AddMember("owner",              static_cast<int>(c.getPlayer()),         a);
        o.AddMember("is_constructing",    isConstructing ? 1 : 0,                  a);
        o.AddMember("turns_until_ready",  turnsUntilReady,                         a);
        o.AddMember("is_blocking",        blocking ? 1 : 0,                        a);
        o.AddMember("ability_used",       (assigned && !blocking) ? 1 : 0,         a);
        o.AddMember("current_hp",         currentHp,                               a);
        o.AddMember("hp_fraction",        hpFraction,                              a);
        o.AddMember("is_frozen",          (chill > 0) ? 1 : 0,                     a);
        o.AddMember("lifespan_remaining", lifespanRem,                            a);
        o.AddMember("stamina_remaining",  charge,                                  a);
        return o;
    }
}

std::string buildV2RecordJSON(const GameState & state, int plyIndex)
{
    rapidjson::Document doc;
    doc.SetObject();
    auto & a = doc.GetAllocator();

    addStr(doc, "schema_version", std::string("v2"), a);
    doc.AddMember("ply_index", plyIndex, a);

    // ---- card_set: the ADVANCED (non-base) buyable units (random units in play) ----
    // Built here from the buy panel; matches serializeState's finalize cardSet notion.
    rapidjson::Value cardSet(rapidjson::kArrayType);
    {
        const CardID numBuyable = state.numCardsBuyable();
        for (CardID i = 0; i < numBuyable; ++i)
        {
            const CardType ct = state.getCardBuyableByIndex(i).getType();
            if (!ct.isBaseSet())
            {
                const std::string & ui = ct.getUIName();
                rapidjson::Value n(ui.c_str(), static_cast<rapidjson::SizeType>(ui.size()), a);
                cardSet.PushBack(n, a);
            }
        }
    }
    doc.AddMember("card_set", cardSet, a);

    // ---- instances: one per ALIVE instance for both players ----
    rapidjson::Value instances(rapidjson::kArrayType);
    for (PlayerID p = 0; p < 2; ++p)
    {
        const CardIDVector & ids = state.getCardIDs(p);
        for (size_t i = 0; i < ids.size(); ++i)
        {
            const Card & c = state.getCardByID(ids[i]);
            if (c.isDead()) continue;   // match JS filter: deadness !== ALIVE
            instances.PushBack(instToRichUnit(c, a), a);
        }
    }
    doc.AddMember("instances", instances, a);

    // ---- supply: { UIName: [whiteRemaining, blackRemaining, inSet], ... } ----
    // JS semantics: include a unit if ws>0 || bs>0 || inSet. Emit REMAINING supply.
    rapidjson::Value supply(rapidjson::kObjectType);
    {
        const CardID numBuyable = state.numCardsBuyable();
        for (CardID i = 0; i < numBuyable; ++i)
        {
            const CardBuyable & cb = state.getCardBuyableByIndex(i);
            const CardType ct = cb.getType();
            const std::string & ui = ct.getUIName();

            const int ws = static_cast<int>(cb.getSupplyRemaining(Players::Player_One));
            const int bs = static_cast<int>(cb.getSupplyRemaining(Players::Player_Two));
            // in_card_set=1 for EVERY buyable unit (base included). This loop is already over
            // numCardsBuyable() (the per-game buy box = base + advanced randomizer; created
            // tokens are not buyable, so excluded), so marking all of them 1 matches BOTH
            // C++ inference (NeuralNet.cpp ~591) and the JS extractor (base via card.baseSet +
            // this game's randomizer). The previous `!isBaseSet()` wrongly dropped base units
            // to 0, an advanced-only convention that diverged from inference.
            const int inSet = 1;

            if (ws > 0 || bs > 0 || inSet)
            {
                rapidjson::Value arr(rapidjson::kArrayType);
                arr.PushBack(ws, a);
                arr.PushBack(bs, a);
                arr.PushBack(inSet, a);
                rapidjson::Value key(ui.c_str(), static_cast<rapidjson::SizeType>(ui.size()), a);
                supply.AddMember(key, arr, a);
            }
        }
    }
    doc.AddMember("supply", supply, a);

    // ---- resources + attack ----
    doc.AddMember("p0_resources", manaToResources(state, Players::Player_One, a), a);
    doc.AddMember("p1_resources", manaToResources(state, Players::Player_Two, a), a);
    doc.AddMember("p0_attack",
                  static_cast<int>(state.getResources(Players::Player_One).amountOf(Resources::Attack)), a);
    doc.AddMember("p1_attack",
                  static_cast<int>(state.getResources(Players::Player_Two).amountOf(Resources::Attack)), a);

    // ---- turn metadata ----
    // C++ m_turnNumber: init 0, +1 per Confirm phase — identical convention to JS numTurns (no offset/skew).
    doc.AddMember("turn_number",   static_cast<int>(state.getTurnNumber()),   a);
    doc.AddMember("active_player", static_cast<int>(state.getActivePlayer()), a);

    // ---- ig_present: does the ACTIVE player have >=1 ALIVE Infusion Grid at turn-start? ----
    // Infusion Grid's engine codename is "Hotel" (getName()); getUIName() is "Infusion Grid".
    // RL action-coverage analysis (Task 5) keys the IG-click-count distribution off boards where
    // the mover actually owns an IG. Computed cheaply from the turn-start state.
    {
        const PlayerID active = state.getActivePlayer();
        bool igPresent = false;
        const CardIDVector & activeIDs = state.getCardIDs(active);
        for (size_t i = 0; i < activeIDs.size(); ++i)
        {
            const Card & c = state.getCardByID(activeIDs[i]);
            if (c.isDead()) continue;
            if (c.getType().getName() == "Hotel") { igPresent = true; break; }
        }
        doc.AddMember("ig_present", igPresent ? 1 : 0, a);
    }

    rapidjson::StringBuffer buffer;
    rapidjson::Writer<rapidjson::StringBuffer> writer(buffer);
    doc.Accept(writer);
    return std::string(buffer.GetString(), buffer.GetSize());
}

} // namespace Prismata
