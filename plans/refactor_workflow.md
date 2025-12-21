# Refactor Story Creation Workflow

## 1. Workflow Overview

The new workflow enforces a structured progression from abstract idea to concrete script, tailored for **Visual Novels (AVG) / Narrative RPGs**.

```mermaid
graph LR
    A[Logline] --> B[World & Characters]
    B --> C[Synopsis]
    C --> D[Beat Sheet (Emotional Arc)]
    D --> E[Outline]
    E --> F[Script]
```

## 2. Analysis & Design

### Step 1: Logline (MuseAgent Refactor)

**Current State**: `MuseAgent` outputs a markdown formatted "Creative Seed".
**Goal**: Enhance `MuseAgent` to focus on inspiration expansion for **Visual Novels**, emphasizing imagery, atmosphere, and player immersion.

**Design**:
- **Action**: Keep `MuseAgent` outputting **Markdown format**.
- **Content Focus**:
    - **核心概念 (High Concept)**: The "Hook" (Logline).
    - **核心设问 (Thematic Question)**: The philosophical or emotional question the story explores (e.g., "Can AI truly love?").
    - **情感基调 (Mood & Tone)**: Atmosphere (e.g., "Cyberpunk Noir", "Cozy Cottagecore").
    - **视觉意象 (Visuals)**: Key scenes/images (Crucial for Visual Novels).
    - **戏剧冲突 (Conflict)**: Core tension.
    - **潜在发展 (Potential)**: Possible directions (Single route or minor branches).
- **Logline Extraction**: Ensure the "High Concept" or "Logline" is clearly marked at the end for programmatic extraction.

### Step 2: Synopsis

**Goal**: Expand the Logline + World + Characters into a full narrative summary.

**Structure (JSON)**:
```json
{
  "title": "Working Title",
  "logline": "Refined Logline",
  "synopsis_text": "A multi-paragraph summary covering beginning, middle, and end.",
  "themes": ["Theme A", "Theme B"],
  "pacing_guide": "Slow burn / Fast paced"
}
```

### Step 3: Beat Sheet (Emotional Arc)

**Goal**: Break the Synopsis into structural beats, focusing on the **Player/Reader's Emotional Experience**.

**Context**: For Visual Novels, "Beats" often correspond to key scenes or dialogue blocks.

**New Structure (JSON)**:
```json
{
  "beats": [
    {
      "beat_id": 1,
      "beat_type": "Inciting Incident",
      "narrative_action": "Protagonist receives the mysterious letter.",
      "emotional_goal": "Curiosity / Unease",
      "reader_experience": "The player should feel intrigued but slightly unsettled by the letter's contents.",
      "tension_level": "Medium" 
    }
  ],
  "global_emotional_arc": "From curiosity to horror to acceptance."
}
```

### Step 4: Outline Generation

**Goal**: Convert the Beat Sheet into a Chapter/Scene tree.

**Prompt Strategy Update**:
- **Input**: Pass the *entire* Beat Sheet JSON.
- **Instruction**: Map Beats to Chapters/Scenes.
- **Constraint**: Ensure every chapter serves a beat.

**Updated Outline Node Structure**:
```json
{
  "id": "chapter_1",
  "type": "chapter",
  "title": "Chapter 1: The Letter",
  "mapped_beats": [1],
  "emotional_target": "Curiosity",
  "description": "...",
  "children": [...]
}
```

## 3. Frontend Concept: Beat Sheet Visualizer

**Visual Metaphor**: "Emotional Seismograph" / "Narrative Wave".

1.  **Layout**: Horizontal scrollable timeline.
2.  **Nodes**: Cards representing Beats.
3.  **Visuals**: Color coding based on `emotional_goal`.
4.  **Interaction**: Drag & drop, edit, sync to Outline.

## 4. Implementation Plan

1.  **Backend**:
    - Update `MuseAgent` prompt (Markdown output, Visual Novel focus, Thematic Question).
    - Update `ShowrunnerAgent` prompts for `generate_beat_sheet` (JSON, Emotional Goals) and `generate_outline` (Beat Mapping).
    - Update `ShowrunnerAgent` code to handle new structures.
2.  **Frontend**:
    - Update `BeatSheetView.vue` and components.