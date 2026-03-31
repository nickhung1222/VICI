# Research Papers Extracted - Index

## R&D-Agent-Quant (arXiv 2505.15155)

**Paper Title**: R&D-Agent-Quant: A Multi-Agent Framework for Data-Centric Factors and Model Joint Optimization

**Authors**: 
- Yuante Li (Carnegie Mellon University)
- Xu Yang, Xiao Yang, Weiqing Liu, Jiang Bian (Microsoft Research Asia)
- Minrui Xu (Hong Kong University of Science and Technology)
- Xisen Wang (University of Oxford)

**Publication**: 39th Conference on Neural Information Processing Systems (NeurIPS 2025)

**Code Repository**: https://github.com/microsoft/RD-Agent

### Extraction Documents

1. **R_D_Agent_Quant_Complete_Extraction.md** (21 KB)
   - Comprehensive 11-section technical report
   - All experimental details and numerical results
   - Architecture breakdown with mathematical formulations
   - Full ablation study and limitations analysis
   - Best for: In-depth understanding and implementation

2. **R_D_Agent_Quick_Reference.txt** (9.7 KB)
   - Quick lookup tables and summaries
   - Five-unit architecture visual flow
   - Performance comparison charts
   - Reproducibility checklist
   - Best for: Quick reference and fact-checking

### Key Findings Summary

**Core Innovation**: 
- Five-unit autonomous R&D framework (Specification→Synthesis→Implementation→Validation→Analysis)
- Co-STEER agent for domain-specific code generation
- Knowledge Forest for cumulative learning
- Contextual bandit scheduler for adaptive optimization

**Performance Results**:
- 3.93X higher annualized returns vs best baseline
- 3.15X better Sharpe ratio
- 7.66X better Calmar ratio
- 69% smaller maximum drawdowns
- 70% fewer factors with superior performance

**Test Period**: 2024-2025 (out-of-sample) across CSI 300/500, NASDAQ 100

**Reproducibility**: Fully open-source with detailed replication checklist

### Quick Navigation

- **Motivation**: See Section 1 (3 critical limitations of current quant pipelines)
- **Architecture**: See Section 2 (detailed breakdown of five units)
- **Performance**: See Section 6 (all numerical results and comparisons)
- **Ablation Study**: See Section 7 (component contributions)
- **Reproducibility**: See Section 9 (checklist and requirements)

---

*Document Index Last Updated: March 30, 2026*
