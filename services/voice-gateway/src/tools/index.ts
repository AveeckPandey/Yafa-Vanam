/**
 * Yafa tool registry - Phase 2 milestone: INTENTIONALLY EMPTY.
 *
 * The sample's weather/wiki tools are deliberately NOT carried over:
 * they are irrelevant to YAFA VANAM and each one is an extra failure mode.
 * Phase 3 will register the real Yafa tools here, in dependency order:
 *
 *   search_product_knowledge()  -> Bedrock KB / existing pgvector RAG
 *   recommend_makeup()          -> FastAPI recommendation engine
 *   analyze_complexion()        -> FastAPI CV (deterministic, 24-shade system)
 *   analyze_outfit()            -> FastAPI outfit colour analysis
 *   get_user_profile()          -> Go API
 *   check_inventory()/get_product()/add_to_bag() -> Go API ONLY
 *
 * With zero registered tools, promptStart advertises an empty tool list and
 * the model behaves as a pure voice assistant - exactly right for milestone 1.
 */
import { ToolRegistry } from './Tool';

export type { Tool, ToolSpec } from './Tool';
export { ToolRegistry } from './Tool';

export function createYafaToolRegistry(): ToolRegistry {
    const registry = new ToolRegistry();
    // Phase 3: registry.register(recommendMakeupTool); etc.
    return registry;
}
