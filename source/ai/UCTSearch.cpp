#include "UCTSearch.h"
#include "AllPlayers.h"
#include <math.h>
#include <algorithm>
#include "AITools.h"
#include "NeuralNet.h"
#include "MoveSampler.h"
#include "Random.h"

using namespace Prismata;

UCTSearch::UCTSearch(const UCTSearchParameters & params) 
    : _params(params)
{
}

void UCTSearch::updateResults(bool forceUpdate)
{
    if (forceUpdate || (_results.traversals && (_results.traversals % 200 == 0)))
    {
        _results.timeElapsed = _searchTimer.getElapsedTimeInMilliSec();
        _results.treeSize = _rootNode.memoryUsed() * _results.nodesCreated;

        UCTNode * bestNode = getBestRootNode(false);
        std::stringstream ss;
        ss << "Possible Moves: " << _rootNode.numChildren() << "\n";
        ss << bestNode->getDescription();
        _results.bestMoveDescription = ss.str();
    }
}

bool UCTSearch::searchShouldStop()
{
    // check search timeout
    if (_results.traversals && (_results.traversals % 10 == 0))
    {
        if (_params.timeLimit() && (_searchTimer.getElapsedTimeInMilliSec() >= _params.timeLimit()))
        {
            return true;
        }
    }

    if (_params.maxTraversals() && (_results.traversals >= _params.maxTraversals()))
    {
        return true;
    }

    return false;
}

void UCTSearch::doSearch(const GameState & initialState, Move & move)
{
    // Reset root diagnostics to their "not available" defaults so a degenerate turn
    // (root ends up with 0 children, so getBestRootNode never writes them) cannot leave
    // stale prior-turn indices to be stamped onto the current record. These are
    // DIAGNOSTIC-only fields (default -1 / empty); resetting them does not affect search.
    _lastChosenIdx = -1;
    _lastArgmaxIdx = -1;
    _lastRootVisits.clear();
    _rootTruncated = false;

    _searchTimer.start();
    _rootNode = UCTNode(NULL, initialState, Players::Player_None, Move(), _params);

    // If PUCT is enabled, generate all root children and compute policy priors
    if (_params.usePUCT())
    {
        _rootNode.generateAllChildren(_params);
        computeRootPriors();
    }

    // do the traversals
    for (_results.traversals = 0; !searchShouldStop(); ++_results.traversals)
    {
        //GameState state(initialState);
        traverse(_rootNode);//, state);

        updateResults();
    }

    // Observe-only root-truncation telemetry. Computed AFTER the traversal loop (in
    // non-PUCT mode root children expand lazily during traverse(), so the root child set
    // and iterator pending-state are only final here) and BEFORE getBestRootNode(true).
    // True iff the MaxChildren cap bound while the move iterator still had candidates.
    // Does NOT change search behaviour or move selection.
    _rootTruncated = _rootNode.wasChildGenerationTruncated();

    // choose the move to return
    UCTNode * bestNode = getBestRootNode(true);
    move = bestNode->getMove();

    updateResults(true);
}

UCTNode * UCTSearch::getBestRootNode(bool allowSampling)
{
    // Capture root diagnostics ONLY on the real move-selection call (allowSampling==true).
    // The win-rate / description paths pass false and must not perturb anything (incl. these).
    if (allowSampling && _rootNode.numChildren() > 0)
    {
        _lastRootVisits.resize(_rootNode.numChildren());
        size_t maxVisits = 0;
        _lastArgmaxIdx = 0;
        for (size_t c = 0; c < _rootNode.numChildren(); ++c)
        {
            const size_t v = _rootNode.getChild(c).numVisits();
            _lastRootVisits[c] = v;
            if (v > maxVisits)
            {
                maxVisits = v;
                _lastArgmaxIdx = (int)c;
            }
        }
    }

    // Self-play-only root sampling. Two regimes:
    //   - Opening (turnNumber < K): tau-temperature + epsilon-uniform mix (unchanged).
    //   - Late game (turnNumber >= K): ONLY when EpsilonLate > 0 — tau->argmax keeps the bulk
    //     greedy while a small persistent EpsilonLate gives recurring decisions (e.g. Infusion
    //     Grid) a chance to be explored all game.
    // CRITICAL: when EpsilonLate == 0 (default) the late-game case is NOT entered (the
    // "|| epsilonLate > 0" guard ensures this), so behaviour — including the number of
    // Random::Real01() draws — is byte-identical to before.
    // Only fires on the real move-selection call (allowSampling); the description/win-rate
    // paths pass false so they don't perturb the seeded RNG stream.
    const bool inOpening = _rootNode.getState().getTurnNumber() < _params.temperatureK();
    if (allowSampling
        && _params.selfPlaySampling()
        && _rootNode.numChildren() > 0
        && (inOpening || _params.epsilonLate() > 0.0))
    {
        // Choose (tau, eps) by phase.
        double tau;
        double eps;
        if (inOpening)
        {
            tau = _params.temperatureTau();   // opening regime, unchanged
            eps = _params.epsilonUniform();
        }
        else
        {
            tau = 1e-9;                        // argmax-equivalent: bulk stays greedy
            eps = _params.epsilonLate();       // small persistent uniform-exploration chance
        }

        std::vector<size_t> visits(_rootNode.numChildren());
        for (size_t c = 0; c < _rootNode.numChildren(); ++c)
        {
            visits[c] = _rootNode.getChild(c).numVisits();
        }
        const double u1 = Random::Real01();
        const double u2 = Random::Real01();
        const size_t idx = MoveSampler::sampleRootIndex(
            visits, tau, eps, u1, u2);
        _lastChosenIdx = (int)idx;
        return &_rootNode.getChild(idx);
    }

    // Default (eval/deploy and late-game self-play): argmax.
    UCTNode * bestNode = NULL;
    if (_params.rootMoveSelectionMethod() == UCTMoveSelect::HighestValue)
    {
        bestNode = &_rootNode.bestUCTValueChild(true, _params);
    }
    else if (_params.rootMoveSelectionMethod() == UCTMoveSelect::MostVisited)
    {
        bestNode = &_rootNode.mostVisitedChild();
    }

    if (allowSampling && bestNode != NULL)
    {
        for (size_t c = 0; c < _rootNode.numChildren(); ++c)
        {
            if (&_rootNode.getChild(c) == bestNode)
            {
                _lastChosenIdx = (int)c;
                break;
            }
        }
    }

    return bestNode;
}

double UCTSearch::getBestRootWinRate()
{
    UCTNode * best = getBestRootNode(false);
    if (best && best->numVisits() > 0)
    {
        return best->numWins() / (double)best->numVisits();
    }
    return 0.5;
}

bool UCTSearch::searchTimeOut()
{
    return (_params.timeLimit() && (_searchTimer.getElapsedTimeInMilliSec() >= _params.timeLimit()));
}

const UCTNode & UCTSearch::getRootNode()
{
    return _rootNode;
}

bool UCTSearch::isTerminalState(GameState & state, const size_t & depth) const
{
    return (depth <= 0 || state.isGameOver());
}

UCTNode & UCTSearch::UCTNodeSelect(UCTNode & node)
{
    UCTNode *   bestNode    = nullptr;
    bool        maxPlayer   = node.getChild(0).getPlayerWhoMoved() == _params.maxPlayer();
    double      bestVal     = std::numeric_limits<double>::lowest();

    // PUCT mode: Q(s,a) + c * P(s,a) * sqrt(N_parent) / (1 + N_child)
    // All children (visited and unvisited) are compared by this formula.
    // Unvisited children use Q = 0.5 (neutral prior).
    if (_params.usePUCT())
    {
        double sqrtParent = sqrt((double)node.numVisits());
        for (size_t c(0); c < node.numChildren(); ++c)
        {
            UCTNode & child = node.getChild(c);
            double prior = child.getPolicyPrior();

            double currentVal;
            if (child.numVisits() > 0)
            {
                double winRate = (double)child.numWins() / (double)child.numVisits();
                double exploration = _params.cValue() * prior * sqrtParent / (1.0 + child.numVisits());
                currentVal = maxPlayer ? (winRate + exploration) : (1.0 - winRate + exploration);
            }
            else
            {
                // Unvisited: Q = 0.5, full exploration bonus
                double exploration = _params.cValue() * prior * sqrtParent;
                currentVal = 0.5 + exploration;
            }

            child.setUCTVal(currentVal);

            if (currentVal > bestVal)
            {
                bestVal = currentVal;
                bestNode = &child;
            }
        }

        return *bestNode;
    }

    // Standard UCB1 mode
    for (size_t c(0); c < node.numChildren(); ++c)
    {
        UCTNode & child = node.getChild(c);

        // if we have visited this node already, get its UCT value
        if (child.numVisits() > 0)
        {
            double winRate = (double)child.numWins() / (double)child.numVisits();
            double uctVal = _params.cValue() * sqrt( log( (double)node.numVisits() ) / ( child.numVisits() ) );
            double currentVal = maxPlayer ? (winRate + uctVal) : (1-winRate + uctVal);

            child.setUCTVal(currentVal);

            // choose the best node
            if (currentVal > bestVal)
            {
                bestVal = currentVal;
                bestNode = &child;
            }
        }
        else
        {
            // if we haven't visited it yet, return it and visit immediately
            return child;
        }
    }

    return *bestNode;
}


void UCTSearch::computeRootPriors()
{
    if (_rootNode.numChildren() == 0)
    {
        return;
    }

    // Use per-player NeuralNet instance if available, else fall back to global singleton
    NeuralNet * nnPtr = _params.getNeuralNet();
    NeuralNet & nn = nnPtr ? *nnPtr : NeuralNet::Instance();
    if (!nn.isLoaded())
    {
        // No neural net loaded — leave uniform priors
        return;
    }

    // Run full neural net (policy + value) on the root state
    NeuralNet::NeuralOutput output = nn.evaluate(_rootNode.getState());
    const std::vector<float> & policy = output.policy;

    // For each child, compute an affinity score based on the buy actions in its move.
    // Score = sum of policy logits for each unit type bought.
    // Then softmax across children to get normalized priors.
    std::vector<double> scores(_rootNode.numChildren(), 0.0);

    for (size_t c = 0; c < _rootNode.numChildren(); ++c)
    {
        UCTNode & child = _rootNode.getChild(c);
        const Move & move = child.getMove();
        double score = 0.0;

        for (size_t a = 0; a < move.size(); ++a)
        {
            const Action & action = move.getAction(a);
            if (action.getType() == ActionTypes::BUY)
            {
                // action.getID() is the CardBuyable index
                const CardBuyable & cb = _rootNode.getState().getCardBuyableByID(action.getID());
                int unitIdx = nn.getUnitIndex(cb.getType().getID());
                if (unitIdx >= 0 && unitIdx < (int)policy.size())
                {
                    score += policy[unitIdx];
                }
            }
        }

        scores[c] = score;
    }

    // Softmax to get normalized priors
    double maxScore = *std::max_element(scores.begin(), scores.end());
    double sumExp = 0.0;
    for (size_t c = 0; c < scores.size(); ++c)
    {
        scores[c] = exp(scores[c] - maxScore);  // numerically stable softmax
        sumExp += scores[c];
    }

    for (size_t c = 0; c < _rootNode.numChildren(); ++c)
    {
        double prior = scores[c] / sumExp;
        _rootNode.getChild(c).setPolicyPrior(prior);
    }
}

double UCTSearch::traverse(UCTNode & node)
{
    double stateEval;

    const GameState & currentState = node.getState();

    // if we haven't visited this node yet
    if ((&node != &_rootNode) && (node.numVisits() == 0))
    {
        if (_params.evalMethod() == EvaluationMethods::NeuralNet)
        {
            // Neural net returns value from active player's perspective [-1,1]
            // Convert to [0,1] win probability from maxPlayer's perspective
            NeuralNet * nnPtr = _params.getNeuralNet();
            NeuralNet & nn = nnPtr ? *nnPtr : NeuralNet::Instance();
            double nnValue = nn.evaluateValue(currentState, _params.maxPlayer());
            stateEval = (nnValue + 1.0) / 2.0;
        }
        else if (_params.evalMethod() == EvaluationMethods::NeuralNetPlusPlayout)
        {
            // Blend neural net and playout evaluations
            NeuralNet * nnPtr = _params.getNeuralNet();
            NeuralNet & nn = nnPtr ? *nnPtr : NeuralNet::Instance();
            double nnValue = nn.evaluateValue(currentState, _params.maxPlayer());
            double nnEval = (nnValue + 1.0) / 2.0;

            PlayerID winner = Eval::PerformPlayout(currentState, _params.getPlayoutPlayer(Players::Player_One), _params.getPlayoutPlayer(Players::Player_Two));
            double playoutEval;
            if (winner == _params.maxPlayer())
                playoutEval = 1.0;
            else if (winner == Players::Player_None)
                playoutEval = 0.5;
            else
                playoutEval = 0.0;

            double w = _params.blendWeight();
            stateEval = w * nnEval + (1.0 - w) * playoutEval;
        }
        else
        {
            PlayerID winner = Eval::PerformPlayout(currentState, _params.getPlayoutPlayer(Players::Player_One), _params.getPlayoutPlayer(Players::Player_Two));
            if (winner == _params.maxPlayer())
                stateEval = 1.0;
            else if (winner == Players::Player_None)
                stateEval = 0.5;
            else
                stateEval = 0.0;
        }
        _results.nodesVisited++;
    }
    // otherwise we have seen this node before
    else
    {
        // if the state is terminal
        if (currentState.isGameOver())
        {
            PlayerID winner = currentState.winner();
            if (winner == _params.maxPlayer())
                stateEval = 1.0;
            else if (winner == Players::Player_None)
                stateEval = 0.5;
            else
                stateEval = 0.0;
        }
        else
        {
            node.generateNextChild(_params);

            UCTNode & next = UCTNodeSelect(node);
            stateEval = traverse(next);
        }
    }

    node.incVisits();
    _results.totalVisits++;
    node.addWins(stateEval);

    return stateEval;
}

// generate the children of state 'node'
// state is the GameState after node's moves have been performed
void UCTSearch::generateChildren(UCTNode & node, GameState & state)
{
    ////node.generateAllChildren(_params);

    //const PlayerID playerToMove(state.getActivePlayer());

    //MoveIteratorPtr iterCopy = _params.getMoveIterator(playerToMove)->clone();
    //iterCopy->setState(state);
    //Move movePerformed;

    //GameState child;  
    //size_t childNum = 0;
    //while (iterCopy->generateNextChild(child, movePerformed) && (_params.maxChildren() == 0 || childNum < _params.maxChildren()))
    //{
    //    UCTNode child(&node, playerToMove, movePerformed, _params);
    //    node.addChild(child);

    //    _results.nodesCreated++;
    //    childNum++;
    //}
}

bool UCTSearch::isRoot(UCTNode & node) const
{
    return &node == &_rootNode;
}

void UCTSearch::printSubTree(const UCTNode & node, GameState s, std::string filename, size_t maxDepth)
{
    GraphViz::Graph G("g");
    G.set("bgcolor", "#ffffff");

    printSubTreeGraphViz(node, G, s, maxDepth, 0);

    G.printToFile(filename);
}

void UCTSearch::printSubTreeGraphViz(const UCTNode & node, GraphViz::Graph & g, GameState state, size_t maxDepth, size_t depth)
{
    state.doMove(node.getMove());

    std::stringstream label;
    std::stringstream move;
    bool detailed = false;

    //move << node.getMove().toString();
    //move << AITools::GetMoveString(node.getMove(), state);

    if (node.getMove().size() == 0)
    {
        move << "root\n";
    }

    label << node.getUCTVal() << "\n";
    label << "v=" << node.numVisits() << ", w=" << node.numWins() << "\n\n";

    const Move & m = node.getMove();
    for (size_t a(0); a < m.size(); ++a)
    {
        const Action & action = m.getAction(a);

        if (action.getType() == ActionTypes::BUY)
        {
            const CardBuyable & cb = state.getCardBuyableByID(action.getID());
            move << cb.getType().getUIName() << "\n";
        }
    }

    label << move.str();

    if (detailed)
    {
        label << node.getUCTVal() << "\n";
        label << "v=" << node.numVisits() << ", w=" << node.numWins() << "\n\n";
        label << move.str() << "-------------\n";
        label << node.getDescription() << "\n\n";

        if (state.getResources(Players::Player_One).getIntString().size() > 0)
        {
            label << state.getResources(Players::Player_One).getIntString() << "\n";
        }
        label << AITools::GetTypeString(Players::Player_One, state) << "\n";

        if (state.getResources(Players::Player_Two).getIntString().size() > 0)
        {
            label << state.getResources(Players::Player_Two).getIntString() << "\n";
        }
    }

    //label << AITools::GetTypeString(Players::Player_One, state);
    //label << AITools::GetTypeString(Players::Player_Two, state);

    std::string fillcolor       ("#aaaaaa");

    if (node.getPlayerWhoMoved() == Players::Player_One)
    {
        fillcolor = "#ff0000";
    }
    else if (node.getPlayerWhoMoved() == Players::Player_Two)
    {
        fillcolor = "#00ff00";
    }
    
    GraphViz::Node n(getNodeIDString(node));
    n.set("label",      label.str());
    n.set("fillcolor",  fillcolor);
    n.set("color",      "#000000");
    n.set("fontcolor",  "#000000");
    n.set("style",      "filled,bold");
    n.set("shape",      "box");
    g.addNode(n);

    if (depth > maxDepth)
    {
        return;
    }

    // recurse for each child
    for (size_t c(0); c<node.numChildren(); ++c)
    {
        const UCTNode & child = node.getChild(c);
        if (child.numVisits() > 0)
        {
            GraphViz::Edge edge(getNodeIDString(node), getNodeIDString(child));
            g.addEdge(edge);
            printSubTreeGraphViz(child, g, state, maxDepth, depth + 1);
        }
    }
}
 
std::string UCTSearch::getNodeIDString(const UCTNode & node)
{
    std::stringstream ss;
    ss << (unsigned long long)&node;
    return ss.str();
}

UCTSearchResults & UCTSearch::getResults()
{
    return _results;
}

std::string UCTSearch::getDescription()
{
    std::stringstream ss;

    #ifdef PRISMATA_FLASH_VERSION
        ss << _results.traversals << "traversals performed at " << ((double)_results.traversals / _results.timeElapsed * 1000) << " traversals per second!";
    #else
        ss << _params.getDescription();
        ss << _results.getDescription();
    #endif


    return ss.str();
}