import { ToolRegistry } from './Tool';
import { createYafaKnowledgeTool } from './YafaKnowledgeTool';

export type { Tool, ToolSpec } from './Tool';
export { ToolRegistry } from './Tool';

export function createYafaToolRegistry(): ToolRegistry {
    const registry = new ToolRegistry();
    // Read-only knowledge retrieval is the first production tool. Product
    // selection, vision and commerce remain separate future tools so retrieval
    // can never accidentally become a source of ranking or live truth.
    registry.register(createYafaKnowledgeTool());
    return registry;
}
