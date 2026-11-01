# Engine strategies and evidence boundaries

| Input | Possible strategy | Evidence needed before claiming support |
| --- | --- | --- |
| Unity Mono IL | Replace the required engine API and run original IL under compatible Mono | Exact game/Unity build, complete API and serialized-data contracts, behavior tests and device measurements. Kingdom New Lands is one title-specific example, not a universal Unity runtime. |
| Unity IL2CPP | Reuse compatible source/runtime or perform title-specific native reconstruction | Architecture, native libraries, graphics/physics dependencies and practical implementation plan. Managed-folder heuristics cannot establish support. |
| MonoGame/XNA/FNA | Adapt a compatible framework or implement the exercised drawing/input/audio API | Exact framework/content version, XNB readers, native dependencies and game slice running on the target. The Unity helpers are not an XNA shim generator. |
| GameMaker | A compatible runner or title-specific reconstruction | VM versus compiled YYC, exact runner version/architecture, working runtime and data reader. A data.win file alone is not runnable support. |
| Godot | An actual graphics backend/runtime adaptation or reconstruction | Exact engine version and required modules/shaders. A headless/server build alone does not render a game. Godot 3 and 4 build arguments/backends differ. |
| Source-available C/C++ | Cross-compile and adapt platform/rendering/audio dependencies | Source completeness, ABI and measured memory/frame cost. Native binary availability alone does not imply source can simply be recompiled. |
| Software 3D | Existing software renderer or a carefully bounded port | Workload measurements; lack of a 3D GPU is not proof that all 3D is impossible. |

There are no validated cross-engine transferability percentages. Inspect original containers and native code before judging feasibility; do not substitute disk size for working-set memory. Lower resolution, palette indexing, streaming and MI_GFX are options to benchmark, not mandatory solutions for every title.
