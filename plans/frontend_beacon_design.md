# Frontend Design: Agent Beacon & Communication Visualization

## 1. Overview
This document outlines the design for visualizing the Agent Beacon and Communication system within the Vue.js frontend. The goal is to make the synchronous agent communication invisible (backend-only) to visible and interactive for the user.

## 2. Architecture Changes

### 2.1 New Store: `AgentRuntimeStore`
We will introduce a new Pinia store (`client/src/components/stores/agentRuntimeStore.js`) to handle the ephemeral state of agents.

**State:**
```javascript
state: () => ({
  // Map of agent_id -> BeaconState
  // BeaconState: { isOpen: boolean, allowedIntents: string[] }
  beaconStates: {},
  
  // Map of agent_id -> Array<AgentMessage>
  // AgentMessage: { sender: string, senderInfo: object, intent: string, content: string, timestamp: number }
  messageLogs: {},
  
  // ID of the agent whose logs are currently being viewed
  selectedAgentId: null 
})
```

**Actions:**
*   `fetchRuntimeState()`: Polls the backend for current beacon statuses.
*   `fetchAgentMessages(agentId)`: Fetches message history for a specific agent.
*   `toggleBeacon(agentId, active)`: Sends request to open/close a beacon.

### 2.2 API Requirements (Proposed Endpoints)
The frontend relies on these (to be implemented) API endpoints:

*   `GET /api/agents/runtime/beacons`: Returns a map of `{ agent_id: { is_open: bool, allowed_intents: [] } }`.
*   `GET /api/agents/runtime/messages/{agent_id}`: Returns recent messages for an agent.
*   `POST /api/agents/runtime/beacon/toggle`: Body `{ agent_id: str, active: bool }`.

## 3. UI Component Design

### 3.1 Agent Node Update (`AgentFlowBlueprint.vue`)
We will enhance the existing `agent-node-header` to include the Beacon Indicator.

**Location:** Top-right of the node header, next to the `agent-node-key`.

**Visual State:**
*   **Inactive (Closed)**: A gray, hollow "broadcast" or "radio" icon. Opacity 0.5.
*   **Active (Open)**: A primary-colored (or green) filled icon with a "pulse" animation effect (CSS `box-shadow` or `transform: scale`).

**Interaction:**
*   **Hover**: Tooltip displays:
    *   State: "Beacon Open" / "Beacon Closed"
    *   Allowed Intents: e.g., "Accepts: [script_review, plot_twist]"
*   **Click**: Opens the **Message Log Panel** (see 3.2).

### 3.2 Message Log Panel (`AgentMessageLog.vue`)
A new component to display the communication history. This can be a **Drawer** (sidebar) or a **Modal**. A Drawer is recommended to allow viewing the flow while inspecting logs.

**Layout:**
*   **Header**: Agent Name + Toggle Switch (to manually Open/Close Beacon).
*   **List Area**: Scrollable list of message cards.
    *   **Incoming Message**: Aligned left. Shows Sender Name (with small avatar/icon), Intent (badge), and Content snippet.
    *   **Outgoing Message**: Aligned right.
*   **Footer**: (Optional) "Clear Log" button.

### 3.3 Visualizing Active Communication (Phase 2)
To visualize message flow:
*   Use the existing `connections-layer` SVG.
*   When a message is detected (via polling diff or SSE event), trigger a CSS animation of a "particle" (small circle) traveling along the `path` from Sender Node to Receiver Node.

## 4. Component Hierarchy

```mermaid
graph TD
    A[AgentFlowBlueprint.vue] --> B[BlueprintCanvas]
    B --> C[AgentNode (v-for)]
    C --> D[AgentNodeHeader]
    D --> E[BeaconIndicator (New)]
    
    A --> F[AgentMessageLog Drawer (New)]
    F --> G[MessageList]
    G --> H[MessageItem]
```

## 5. Mockup Details

### Beacon Indicator (CSS)
```css
.beacon-indicator {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  transition: all 0.3s ease;
}

.beacon-indicator.active {
  background-color: var(--spark-success);
  box-shadow: 0 0 8px var(--spark-success-glow);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(var(--spark-success-rgb), 0.7); }
  70% { box-shadow: 0 0 0 10px rgba(var(--spark-success-rgb), 0); }
  100% { box-shadow: 0 0 0 0 rgba(var(--spark-success-rgb), 0); }
}
```

### Message Log Item
```text
[Sender Name] (Intent: Critique)
----------------------------------
"I think the dialogue in scene 2 needs more tension..."
----------------------------------
[Timestamp]
```

## 6. Implementation Steps

1.  **Store Setup**: Create `agentRuntimeStore.js`.
2.  **API Mocking**: Since backend endpoints might not exist yet, mock the API responses in `apiClient.js` or within the store for development.
3.  **Component Creation**:
    *   Create `BeaconIndicator.vue`.
    *   Create `AgentMessageLog.vue` (using `n-drawer`).
4.  **Integration**:
    *   Import and use `BeaconIndicator` in `AgentFlowBlueprint.vue`.
    *   Add the `AgentMessageLog` drawer to `AgentFlowBlueprint.vue`.
    *   Wire up click events.

## 7. Data Flow

1.  **Backend** maintains `CommunicationContext` with active agents.
2.  **Frontend** (Store) polls `GET /api/agents/runtime/beacons`.
3.  **Store** updates `beaconStates`.
4.  **BeaconIndicator** reacts to `beaconStates[id].isOpen` to change color/animation.
5.  **User** clicks Beacon.
6.  **Frontend** opens Drawer and calls `fetchAgentMessages(id)`.
7.  **Drawer** displays message history.

