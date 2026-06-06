'use strict';

/**
 * training_example.js — Shared V2 training-example extractor (single source of truth).
 *
 * Produces the DeepSets V2 per-turn training record from a live JS-engine State
 * (a turn-start snapshot). Used by BOTH:
 *   - matchup_clean.js          (MB self-play / matchup corpus)
 *   - extract_training_jsengine.js (human replay corpus)
 * so the two corpora are produced by IDENTICAL feature code — no convert step, no drift.
 *
 * The record is the per-STATE core. Callers stamp game-level metadata afterwards:
 *   outcome_p0, total_plies, replay_code, rating_p0, rating_p1, game_date.
 *
 * Feature helpers come from state_adapter.js (_instToRichUnit, _manaToResources), the
 * same ones the MB path has always used.
 */

const C = require('./C');
const { _instToRichUnit: instToRichUnit, _manaToResources: manaToResources } = require('./state_adapter');

/**
 * Build the V2 per-turn training record.
 *
 * @param {State}    gameState - live State (analyzer.gameState, or beginTurnHistory[i])
 * @param {string[]} cardSet   - display names of the advanced (non-base) units in the deck
 * @param {number}   plyIndex  - 0-based ply index within the game
 * @returns {Object} V2 record core (without outcome_p0/total_plies/replay_code/ratings/game_date)
 */
function extractTrainingExampleV2(gameState, cardSet, plyIndex) {
    const instances = [];

    gameState.table.forEach((inst) => {
        if (inst.deadness !== C.DEADNESS_ALIVE) return;  // match state_adapter.js pattern
        instances.push(instToRichUnit(inst));
    });

    const p0Mana = gameState.playerMana(C.COLOR_WHITE);
    const p1Mana = gameState.playerMana(C.COLOR_BLACK);

    // Supply — include ALL units in the card set, even sold-out (supply=0).
    // in_card_set flag must persist so the model knows the unit was buyable this game.
    //
    // in_card_set = 1 iff the unit is BUYABLE in this game = base + advanced randomizer,
    // created tokens (Husk, Gauss Charge, ...) excluded. This MUST match C++ inference
    // (NeuralNet.cpp ~581-591, which marks 1 for every numCardsBuyable() = base+advanced)
    // and the C++ self-play exporter (V2Record.cpp). Base units (card.baseSet) are always
    // buyable so are always in-set, regardless of the passed `cardSet` (which lists only the
    // advanced randomizer units, as both the MB config.cardSet and the human randomizer do).
    // Deriving base membership from card.baseSet — not from the cardSet list — keeps this
    // count-agnostic (Base+5 .. Base+11 and larger RL sets) and consistent across BOTH the
    // MB matchup path and the human replay path that share this extractor.
    const supply = {};
    for (let i = 0; i < gameState.cards.length; i++) {
        const card = gameState.cards[i];
        // REMAINING supply, not the initial total. The engine keeps whiteSupply/blackSupply
        // at the constant initial cap and tracks purchases in whiteBought/blackBought, so
        // remaining = total - bought. This MUST match C++ inference (NeuralNet.cpp uses
        // cb.getSupplyRemaining) and the C++ exporter (V2Record.cpp getSupplyRemaining).
        // Writing the raw total here is a train↔inference skew (the model would train on a
        // ~constant cap but evaluate on a decreasing remaining count).
        const ws = Math.max(0, (gameState.whiteSupply[i] || 0) - (gameState.whiteBought[i] || 0));
        const bs = Math.max(0, (gameState.blackSupply[i] || 0) - (gameState.blackBought[i] || 0));
        const inSet = (card.baseSet || cardSet.includes(card.UIName)) ? 1 : 0;
        // Include if unit has supply OR is in the card set (even if sold out)
        if (ws > 0 || bs > 0 || inSet) {
            supply[card.UIName] = [ws, bs, inSet];
        }
    }

    return {
        schema_version: "v2",
        ply_index: plyIndex,
        card_set: cardSet,
        instances: instances,   // per-instance list (includes owner field)
        supply: supply,
        p0_resources: manaToResources(p0Mana),
        p1_resources: manaToResources(p1Mana),
        p0_attack: p0Mana.pool[C.MANA_A],
        p1_attack: p1Mana.pool[C.MANA_A],
        turn_number: gameState.numTurns,
        active_player: gameState.turn
    };
}

module.exports = { extractTrainingExampleV2 };
