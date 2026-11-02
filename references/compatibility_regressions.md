# Compatibility failures worth distinguishing

These checks come from reproduced Kingdom: New Lands adapter failures. Apply the relevant checks to another game; they do not establish general Unity compatibility.

## Import data by type, not field name

A field named `m_FontData` can hold binary font bytes on a Font asset, or a UI.Text layout dictionary with a font reference, alignment, size, wrap and line spacing. Removing every field with that name silently breaks labels and day counters. Preserve structured metadata and add a converter fixture for both meanings. Compare original serialized values with converted values before inventing layout overrides.

A bitmap font's glyph sizes are already baked in font pixels. Keep the distinction between glyph metrics, generation extents, canvas scale and UI.Text.pixelsPerUnit; applying the font scale twice causes buttons and map labels to wrap. Verify actual pause and transition screens as well as isolated text tests.

For existing packs, a narrow metadata repair can avoid reconverting audio/textures. Generate it from a verified owned source and bind it to the exact packed object blobs it repairs. Refuse mismatched entries, preserve saves, and keep owned metadata out of public packages. New conversions should retain the metadata directly.

## Diagnose missing sprites through their mechanism

Check active/enabled state, alpha, sprite reference, hierarchy, world transform and physical position separately. A catapult with visible wheels and missing body had valid opaque body sprites: the chassis fell below the ground because its wheel HingeJoint2D anchors were ignored. Reproduce the original purchase/construction path; instantiating a prefab in a convenient pose missed this failure.

A narrow hinge implementation must preserve connected-body references through cloning, independent world poses for parented rigidbodies, anchor constraints, free axle rotation, and joint collision exclusions. Test support under gravity, motion, disabled joints and destruction. State unsupported motors/limits/breaking explicitly; a free-wheel fix is not a complete joint engine.

Respect serialized camera culling masks. Reflection-camera-only light sprites drawn through the main camera caused a torch streak on land. Compute mesh bounds from transformed vertices: a zero-size MeshRenderer bound also put the reflection axis at the wrong height. Check main, interface and reflection passes independently, including optional lighter visual modes.

An active corpse is not a living enemy. Edge indicators should use the original death state and effective activation, rather than infer life from sprite alpha. A live spawn can temporarily be transparent. Treat clustered-enemy disappearance as a separate report unless the same failure has actually reproduced.

For intermittent visibility, capture the crowd, the same frame with one actor hidden, and the same actor alone with its peers hidden. Zero contributed pixels can be ordinary occlusion: the original Unity player also completely hid live ground enemies behind other enemies and walls. Check bodies and masks separately, and distinguish this control from reproducing a player's invisible-body report. Do not force opacity or reorder actors just because the crowd comparison is ambiguous.

Pool reuse can preserve a terminal death sprite if the replacement engine never clears Animator state on GameObject deactivation. A verified Unity 2017 comparison reset a revived Troll to its default state; the adapter retained Die at normalized time above four and a 32-by-5-pixel terminal sprite. Reset evaluated state after disable callbacks and validate the same naturally dead actor through repeated original Pool calls. A new active alpha-1 renderer alone does not establish a normal body pose. Keep component-only disable semantics separate unless tested.

A persistent replacement HUD must not inherit a transient announcement's fade alpha. Generate a local opaque text-settings copy while retaining the original tint and authoritative day formatter. Check days after the first announcement has faded, including pause and saved-game reload.

## Preserve semantics while optimizing

Record a deterministic workload from a copied later-island save, not only a fresh start. Dense forests, groups of enemies and multiple repair/debris objects exercise different costs. Compare stock-clock frame windows and phase profiles; exclude boot from steady-state claims and label mute/fixed-timestep diagnostic runs.

A broadphase sort cache must preserve ordering of equal-coordinate entries as well as pair membership. Validate moving objects, activation, destruction, and changes in ties against the previous implementation. Skip static/static spans only if those pairs could never produce a response or event.

Query semantics can differ: an existing point query used a cached registry but tested current collider geometry, while an area query used cached bounds. Adding the same bounds-based early exit to both changed same-frame movement behavior. Test a collider moved after the first query, callback-time queries, buffer truncation and exact result ordering.

For transform caches, test local/world writes, ancestor changes, identical writes, reparenting, clone initialization and inverse matrices. Descendant invalidation may avoid rechecking unrelated static forests after every moving body, but every hierarchy-write path must participate. Use randomized trees and fresh matrix composition as an independent oracle, then compare real-game screenshots and state.

Keep optimizations and behavior repairs separable for measurement. An exact physics workload should retain positions, velocities, query counts and events; an intentional repair needs its own expected behavior and actual-game reproduction. Passing microbenchmarks does not establish a device FPS gain or a complete playthrough.

Weather state can affect the economy even when its particles are cosmetic. Retain the original weather/season updates; a bounded presentation may read the current rain/snow intensity and wind without consuming the game's random generator. Use scaled time to freeze the effect during pause, and keep it below menus and HUD. Validate actual winter gameplay separately from a forced-snow rendering probe.

Treat a native import header/index reader as a measured milestone, not a completed installer. Full first-launch preparation still needs build verification, streaming texture/audio/font conversion, pack parity, recoverable staging, an on-screen progress/error path, and an interrupted-import test. Never mark a partial stage ready or overwrite an existing pack/save on failure.
