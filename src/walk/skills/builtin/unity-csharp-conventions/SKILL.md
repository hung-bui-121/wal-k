---
name: unity-csharp-conventions
version: "1.0"
description: C# and Unity conventions for gameplay code - namespaces, assembly definitions, serialization, MonoBehaviour lifecycle, async code and test placement.
scope: KERNEL
applies_to_roles: [SENIOR_DEV, LEAD_DEV]
requires_tools: []
tags: [unity, csharp, conventions]
---
# Unity C# conventions

Follow the project's own conventions (`project.md`, section "Coding Conventions") first. Where
they say nothing, use these.

## Namespaces and assemblies

- One root namespace per game (`<Company>.<Game>`), then one sub-namespace per feature folder.
- Every feature folder under `Assets/` has an assembly definition (`.asmdef`). References go
  one way only: features depend on core, never the reverse. Do not add a reference just to
  silence a compile error; fix the dependency direction instead.
- Editor-only code goes in an `Editor/` folder with an editor-only asmdef.

## Serialization

- Expose inspector fields as `[SerializeField] private` fields, not public fields.
- Renaming a serialized field loses data. Add `[FormerlySerializedAs("oldName")]` when you rename.
- Do not serialize properties, interfaces or dictionaries; Unity cannot. Use explicit
  serializable structs or lists.
- `ScriptableObject` assets hold shared configuration; do not mutate them at runtime.

## MonoBehaviour lifecycle

- `Awake`: own references and caches. `OnEnable`/`OnDisable`: subscribe and unsubscribe to
  events, always symmetric. `Start`: work that needs other objects initialised.
- No `GetComponent`, `Find*` or allocations in `Update`. Cache in `Awake`.
- Use `FixedUpdate` for physics, `Update` for input and `LateUpdate` for camera follow.
- Never rely on execution order between scripts. Use explicit initialisation, or Script
  Execution Order only with a comment explaining why.

## Async code

- Prefer `async`/`await` (UniTask if the project uses it, otherwise `Awaitable`) for
  sequential flows. Pass a `CancellationToken` tied to the object's lifetime
  (`destroyCancellationToken`).
- Coroutines are fine for simple per-frame sequences. Stop them in `OnDisable`.
- Never block the main thread (`.Result`, `.Wait()`, `Thread.Sleep`).
- Unity APIs are main-thread only. Marshal results back before touching objects.

## Tests

- EditMode tests (pure logic, no scene) go in `Tests/EditMode/` with an asmdef that references
  the code under test and `UnityEngine.TestRunner`/`UnityEditor.TestRunner`.
- PlayMode tests (scenes, physics, coroutines) go in `Tests/PlayMode/`.
- Keep gameplay logic in plain C# classes so EditMode tests can cover it. Keep
  MonoBehaviours thin.
- A bug fix comes with a test that fails before the fix.
