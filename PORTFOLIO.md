# Selected work — Cristina Castro

I am an experimental materials chemist completing an Oxford DPhil and building ChimiaDAO. I want scientific work to be easier to inspect, challenge and reproduce, while helping people develop the ability to do difficult research locally.

[Open the portfolio and demo](https://xchemtina.github.io/chimialabs-osi-2026/)

## ChimiaLabs: inspecting structural hypotheses

I led ChimiaLabs with AI assistance. The question comes from my materials research: different copper arrangements can share the same average crystal structure. Which differences can our measurements actually distinguish?

The private research workflow links periodic structures, individual sites, Truchet-style representations and retained calculations. It separates an arrangement from its translation average and preserves the limits of each comparison. We have not established a unique copper ordering. The scientific implementation, data and visual demonstrations remain private.

I submitted ChimiaLabs to the 2026 Open Scientific Intelligence Hackathon. The entry credits Cristina Castro and Larsen James Close. [Public methods](README.md).

## Public diffraction companion: following a result through software

[Open the browser demo](https://xchemtina.github.io/chimialabs-osi-2026/companion/public/) · [Source and reproduction](companion/README.md)

This separate example uses public PbSO4 diffraction data and a recorded native calculation. A deterministic Rust skill in the existing OpenAgents runtime checks the source files, binds a signed result to a signed request, rejects altered evidence and skips an existing result on repeat execution. No model inference is involved in the replay. The viewer displays saved receipts; the CLI recomputes the software checks.

The native calculation predates the adapter, and its poor fit remains visible. This demonstrates software integration and traceable evidence; it does not validate the copper sample or establish a new scientific result. The integration was prepared in October and released in November, separately from the methods-only OSI entry.

## PoSyn / OpenAgents / PoX: preserving what was reviewed

With collaborators and AI tools, I brought these components into a prototype for signed evidence exchange. A review refers to the exact evidence package. Changing the evidence breaks the old review binding; each recipient checks signatures, scope and delegation against its available local policy.

The public demonstration uses synthetic data on one machine. It does not establish physical replication or independent scientific validation. I have also run the integration successfully with Arshath; that joint run is my account, distinct from the public demo record.

[Inspect the pinned prototype and instructions](https://github.com/xchemtina/ethglobal-openagents/blob/7316731bb792c1055688d7ce6be79474a9843285/docs/integrations/posyn-pox/README.md).

## Earlier team recognition

Our earlier projects received Filecoin's Best storage innovation with Filecoin Onchain Cloud, 3rd place, and Protocol Labs' Open Data, Knowledge Graphs & Research Infra award in Buenos Aires; and Polygon's Best Consumer App on Polygon, Runner-up, in San Francisco.

[Buenos Aires organizer record](https://ethglobal.com/showcase/chimiadao-pox-hw7k3) · [San Francisco organizer record](https://ethglobal.com/showcase/chimiadao-xsmjg).

## What comes next

Finishing my DPhil comes first. The longer-term purpose is a federation of capable laboratories sharing methods and evidence. My proposed first physical demonstration is a bounded nonreactive liquid-transfer task. A completed result with independent review and fresh replication by another laboratory are two separate milestones. Access, the reviewer and receiving laboratory still need agreement.
