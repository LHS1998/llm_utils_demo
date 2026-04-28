import Mathlib.MeasureTheory.Integral.Prod
import Mathlib.MeasureTheory.Integral.Bochner.Basic
import Mathlib.MeasureTheory.Measure.Lebesgue
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Topology.Order.Compact
import Mathlib.Data.Real.Basic
import Mathlib.Data.Set.Intervals.Basic
import Mathlib.Tactic

open Real
open Set
open MeasureTheory
open Filter

noncomputable section

-- 定义区域 D = [0,2] × [0,2]
def D : Set (ℝ × ℝ) := Set.Icc (0 : ℝ) 2 ×ˢ Set.Icc (0 : ℝ) 2

-- 计算 b = ∫∫_D |x*y - 1| dσ
def b : ℝ := ∫ p : ℝ × ℝ in D, |p.1 * p.2 - 1|

-- D 是可测集
lemma measurableSet_D : MeasurableSet D :=
  MeasurableSet.prod measurableSet_Icc measurableSet_Icc

-- D 是紧致的
lemma isCompact_D : IsCompact D :=
  isCompact_Icc.prod isCompact_Icc

-- b 是正的
theorem b_pos : 0 < b := by
  refine integral_pos_iff_support_of_nonneg (fun p => abs_nonneg _) ?_ |>.mp ?_
  · refine Continuous.integrableOn_compact isCompact_D ?_
    exact continuous_abs.comp (Continuous.sub (Continuous.mul continuous_fst continuous_snd)
      continuous_const)
  · refine ⟨(1, 1), by simp [D, left_mem_Icc, right_mem_Icc], ?_⟩
    norm_num

-- 存在性定理
theorem exists_point_with_lower_bound (f : ℝ × ℝ → ℝ) (hf : Continuous f)
    (h1 : ∫ p in D, f p = 0) (h2 : ∫ p in D, (p.1 * p.2) * f p = 1) :
    ∃ (ξ : ℝ × ℝ) (hξ : ξ ∈ D), |f ξ| ≥ 1 / b := by
  -- 定义辅助积分 I = ∫∫_D (x*y - 1) f(x,y) dσ
  set I := ∫ p in D, (p.1 * p.2 - 1) * f p with hI_def
  -- 计算 I = 1
  have hI : I = 1 := by
    dsimp [I]
    calc
      ∫ p in D, (p.1 * p.2 - 1) * f p = ∫ p in D, (p.1 * p.2 * f p - f p) := by
        refine integral_congr fun p _ => ?_
        ring
      _ = ∫ p in D, (p.1 * p.2 * f p) - ∫ p in D, f p := by
        rw [integral_sub]
        · exact (Continuous.aestronglyMeasurable (by continuity)).integrableOn
        · exact (Continuous.aestronglyMeasurable hf).integrableOn
      _ = 1 - 0 := by rw [h2, h1]
      _ = 1 := by norm_num
  -- 因此 |I| = 1
  have hI_abs : |I| = 1 := by rw [hI, abs_one]
  -- 反证法：假设结论不成立
  by_contra! H  -- H: ∀ ξ ∈ D, |f ξ| < 1 / b
  -- 由于 f 连续，|f| 在紧集 D 上达到最大值 M
  have h_cont_abs : Continuous (|f ·|) := continuous_abs.comp hf
  rcases isCompact_D.exists_isMaxOn h_cont_abs.continuousOn with ⟨ξ, hξ, hmax⟩
  have hM_lt : |f ξ| < 1 / b := H ξ hξ
  -- 估计 |I|
  calc
    |I| = |∫ p in D, (p.1 * p.2 - 1) * f p| := rfl
    _ ≤ ∫ p in D, |(p.1 * p.2 - 1) * f p| := abs_integral_le_integral_abs
    _ = ∫ p in D, |p.1 * p.2 - 1| * |f p| := by
      refine integral_congr fun p _ => ?_
      rw [abs_mul]
    _ ≤ ∫ p in D, |p.1 * p.2 - 1| * (|f ξ|) := by
      refine integral_mono_on ?_ ?_ measurableSet_D fun p hp => ?_
      · exact (Continuous.aestronglyMeasurable (by continuity)).integrableOn
      · exact (Continuous.aestronglyMeasurable (by continuity)).integrableOn
      · exact mul_le_mul_of_nonneg_left (hmax hp) (abs_nonneg _)
    _ = (|f ξ|) * ∫ p in D, |p.1 * p.2 - 1| := by
      rw [integral_mul_left, mul_comm]
    _ = |f ξ| * b := by simp [b]
    _ < (1 / b) * b := by
      refine mul_lt_mul_of_pos_right hM_lt b_pos
    _ = 1 := by
      field_simp [ne_of_gt b_pos]
  -- 这与 |I| = 1 矛盾
  linarith
