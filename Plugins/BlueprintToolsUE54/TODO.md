# Blueprint Tools UE5.4 - Implementation TODO

## Phase 1: Core Extraction (ExtractBlueprint)

### 1.1 Basic Blueprint Metadata

- [ ] Extract class name, parent class, path
- [ ] Extract Blueprint type (normal, interface, macro library)
- [ ] Extract Blueprint flags and settings
- **Reference**: `BlueprintExtractor/Private/Extractors/BlueprintExtractor.cpp`

### 1.2 Variables Extraction

- [ ] Extract member variables (name, type, default value)
- [ ] Extract variable metadata (category, tooltip, replication)
- [ ] Extract variable flags (expose on spawn, instance editable, etc.)
- [ ] Handle complex types (arrays, maps, sets, structs)
- **Reference**: `BlueprintExtractor/Private/Extractors/BlueprintExtractor.cpp::ExtractVariables()`

### 1.3 Components Extraction

- [ ] Extract component hierarchy
- [ ] Extract component properties
- [ ] Extract component transforms
- [ ] Handle scene components vs actor components
- **Reference**: `BlueprintExtractor/Private/Extractors/BlueprintExtractor.cpp::ExtractComponents()`

### 1.4 Functions Extraction (Shallow)

- [ ] Extract function signatures (name, inputs, outputs)
- [ ] Extract function metadata (category, keywords, tooltip)
- [ ] Extract function flags (pure, const, static, etc.)
- **Reference**: `BlueprintExtractor/Private/Extractors/BlueprintExtractor.cpp::ExtractFunctions()`

### 1.5 Graph Extraction (Full)

- [ ] Extract event graphs
- [ ] Extract function graphs
- [ ] Extract construction script
- [ ] Extract nodes and connections
- [ ] Handle graph filtering by name
- **Reference**: `BlueprintExtractor/Private/Extractors/GraphExtractor.cpp`

### 1.6 Class Defaults (CDO)

- [ ] Extract CDO property values
- [ ] Compare with parent class defaults
- [ ] Only include modified properties
- **Reference**: `BlueprintExtractor/Private/PropertySerializer.cpp`

## Phase 2: Blueprint Creation (CreateBlueprint)

### 2.1 Basic Blueprint Creation

- [x] Create Blueprint from parent class (already implemented)
- [ ] Set Blueprint metadata
- [ ] Handle different Blueprint types
- **Reference**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::CreateBlueprint()`

### 2.2 Parse PayloadJson

- [ ] Parse variables array from JSON
- [ ] Parse functions array from JSON
- [ ] Parse components array from JSON
- [ ] Validate JSON structure
- **Reference**: `BlueprintExtractor/Private/Authoring/AuthoringHelpers.cpp::ParsePayload()`

### 2.3 Create Initial Members

- [ ] Create variables from payload
- [ ] Create function signatures from payload
- [ ] Create components from payload
- [ ] Set default values
- **Reference**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp`

## Phase 3: Blueprint Modification (ModifyBlueprintMembers)

### 3.1 Variable Operations

- [ ] **add_variable**: Add new member variable
  - Parse variable type from JSON
  - Set default value
  - Set metadata (category, tooltip, flags)
  - **Reference**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::AddVariable()`
- [ ] **remove_variable**: Remove existing variable
  - Find variable by name
  - Remove all references (if any)
  - **Reference**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::RemoveVariable()`
- [ ] **modify_variable**: Modify existing variable
  - Update default value
  - Update metadata
  - Update flags
  - **Reference**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::ModifyVariable()`

### 3.2 Function Operations

- [ ] **add_function**: Add new function
  - Create function graph
  - Add input/output parameters
  - Set function metadata
  - **Reference**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::AddFunction()`
- [ ] **remove_function**: Remove existing function
  - Remove function graph
  - Remove all call sites (if any)
  - **Reference**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::RemoveFunction()`
- [ ] **modify_function**: Modify function signature
  - Update parameters
  - Update metadata
  - **Reference**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::ModifyFunction()`

### 3.3 Component Operations

- [ ] **add_component**: Add new component
  - Create component instance
  - Set component properties
  - Attach to hierarchy
  - **Reference**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::AddComponent()`
- [ ] **remove_component**: Remove existing component
  - Remove from hierarchy
  - Clean up references
  - **Reference**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::RemoveComponent()`
- [ ] **modify_component**: Modify component properties
  - Update properties
  - Update transform
  - **Reference**: `BlueprintExtractor/Private/Authoring/BlueprintAuthoring.cpp::ModifyComponent()`

## Phase 4: Type System & Helpers

### 4.1 Type Parsing

- [ ] Parse primitive types (int, float, bool, string, name, text)
- [ ] Parse object references
- [ ] Parse struct types
- [ ] Parse enum types
- [ ] Parse container types (array, set, map)
- **Reference**: `BlueprintExtractor/Private/Authoring/AuthoringHelpers.cpp::ParsePinType()`

### 4.2 Property Serialization

- [ ] Serialize property values to JSON
- [ ] Deserialize JSON to property values
- [ ] Handle nested structures
- [ ] Handle asset references
- **Reference**: `BlueprintExtractor/Private/PropertySerializer.cpp`

### 4.3 Validation

- [ ] Validate variable names (no duplicates, valid identifiers)
- [ ] Validate types (exist and are accessible)
- [ ] Validate default values (match type)
- [ ] Validate component hierarchy
- **Reference**: `BlueprintExtractor/Private/Authoring/AuthoringHelpers.cpp::ValidatePayload()`

## Phase 5: Compilation & Error Handling

### 5.1 Blueprint Compilation

- [x] Basic compilation (already implemented)
- [ ] Collect compilation errors
- [ ] Collect compilation warnings
- [ ] Format error messages for JSON output
- **Reference**: `BlueprintExtractor/Private/Extractors/BlueprintExtractor.cpp::CompileBlueprint()`

### 5.2 Error Response Format

- [ ] Standardize error JSON format
- [ ] Include error location (node, pin, line)
- [ ] Include error severity
- [ ] Include suggested fixes
- **Reference**: `BlueprintExtractor/Private/BlueprintExtractorSubsystem.cpp`

## Phase 6: Asset Management

### 6.1 Asset Search & List

- [x] Basic search (already implemented)
- [x] Basic list (already implemented)
- [ ] Add more filter options
- [ ] Add sorting options
- [ ] Add pagination support

### 6.2 Asset Saving

- [x] Basic save (already implemented)
- [ ] Handle save failures gracefully
- [ ] Mark packages dirty before save
- [ ] Validate assets before save

## Phase 7: Testing & Validation

### 7.1 Unit Tests

- [ ] Test variable creation with all types
- [ ] Test function creation
- [ ] Test component creation
- [ ] Test extraction accuracy

### 7.2 Integration Tests

- [ ] Test full workflow: create → modify → compile → save
- [ ] Test error handling
- [ ] Test with complex Blueprints
- [ ] Test with different parent classes

## Implementation Priority

### High Priority (Core Functionality)

1. Phase 3.1: Variable Operations (add, remove, modify)
2. Phase 4.1: Type Parsing
3. Phase 1.2: Variables Extraction
4. Phase 2.2 & 2.3: PayloadJson parsing and initial member creation

### Medium Priority (Extended Functionality)

5. Phase 3.2: Function Operations
6. Phase 3.3: Component Operations
7. Phase 1.3: Components Extraction
8. Phase 1.4: Functions Extraction

### Low Priority (Advanced Features)

9. Phase 1.5: Graph Extraction (Full)
10. Phase 5: Enhanced compilation and error handling
11. Phase 7: Testing

## Key Reference Files in BlueprintExtractor

### Must Read (Core Implementation)

1. `Private/Authoring/BlueprintAuthoring.cpp` - All authoring operations
2. `Private/Authoring/AuthoringHelpers.cpp` - Type parsing, validation
3. `Private/Extractors/BlueprintExtractor.cpp` - Extraction logic
4. `Private/PropertySerializer.cpp` - Property serialization

### Supporting Files

5. `Private/Extractors/GraphExtractor.cpp` - Graph extraction
6. `Private/BlueprintExtractorSubsystem.cpp` - API entry points
7. `Public/BlueprintExtractorTypes.h` - Type definitions

## Notes

- Always use official UE Blueprint APIs (FBlueprintEditorUtils, FKismetEditorUtilities)
- Never directly modify Blueprint->NewVariables array
- Always compile after modifications
- Always mark packages dirty before saving
- Use FBlueprintEditorUtils::AddMemberVariable() instead of manual array manipulation
- Reference BlueprintExtractor implementation - it's tested and uses official APIs
