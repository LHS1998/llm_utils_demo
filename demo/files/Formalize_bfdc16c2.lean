import Mathlib
open MeasureTheory
open Set
open Real
open Topology

-- 矩形区域 D = [0,2] × [0,2]
def D : Set (ℝ × ℝ) := Set.prod (Set.Icc (0 : ℝ) 2) (Set.Icc (0 : ℝ) 2)

-- D 是紧集
lemma D_compact : IsCompact D := by
  exact isCompact_Icc.prod isCompact_Icc

-- 函数 g(x,y) = |xy - 1|
def g (x : ℝ × ℝ) : ℝ := |x.1 * x.2 - 1|

-- g 是连续函数
lemma g_continuous : Continuous g := by
  unfold g
  continuity

-- g 非负
lemma g_nonneg (x : ℝ × ℝ) : 0 ≤ g x := by
  unfold g
  exact abs_nonneg _

-- 常数 b = ∬_D |xy - 1| dσ
noncomputable def b : ℝ := ∫ (z : ℝ × ℝ) in D, g z

-- b 为正（暂时用 sorry 跳过证明）
lemma b_pos : 0 < b := by
  sorry

-- 主定理 - 修复语法错误版本，严格不等式部分暂用 sorry
theorem exists_point_with_large_f (f : ℝ × ℝ → ℝ) (hf_cont : Continuous f)
    (h_int1 : ∫ z in D, f z = 0)
    (h_int2 : ∫ z in D, (z.1 * z.2) * f z = 1) :
    ∃ (ξ η : ℝ), ((ξ, η) ∈ D) ∧ |f (ξ, η)| ≥ 1 / b := by
  -- 反证法：假设对所有点都有 |f| < 1/b
  by_contra! H  -- H : ∀ (ξ η : ℝ), (ξ, η) ∈ D → |f (ξ, η)| < 1 / b
  -- 转换为 ∀ z ∈ D, |f z| < 1/b
  have h_bound : ∀ z ∈ D, |f z| < 1 / b := by
    intro z hz
    rcases z with ⟨ξ, η⟩
    exact H ξ η hz
  -- 定义辅助函数 h(z) = (z.1 * z.2 - 1) * f(z)
  set h := fun (z : ℝ × ℝ) => (z.1 * z.2 - 1) * f z with hh_def
  -- 证明 h 在 D 上可积
  have h_int_h : IntegrableOn h D := by
    unfold h
    have : Continuous fun z : ℝ × ℝ => (z.1 * z.2 - 1) * f z := by
      continuity
    exact this.continuousOn.integrableOn_compact D_compact
  -- 计算 ∫_D h = ∫_D xy f - ∫_D f = 1 - 0 = 1
  have h_int_val : ∫ z in D, h z = 1 := by
    unfold h
    calc
      ∫ z in D, (z.1 * z.2 - 1) * f z = ∫ z in D, (z.1 * z.2 * f z - f z) := by
        refine integral_congr_ae ?_
        refine ae_of_all (volume.restrict D) fun z => ?_
        ring
      _ = (∫ z in D, z.1 * z.2 * f z) - (∫ z in D, f z) := by
        rw [integral_sub]
        · -- 第一个函数可积
          have h1 : Continuous fun z : ℝ × ℝ => z.1 * z.2 * f z := by
            continuity
          exact h1.continuousOn.integrableOn_compact D_compact
        · -- 第二个函数可积
          exact hf_cont.continuousOn.integrableOn_compact D_compact
      _ = 1 - 0 := by rw [h_int2, h_int1]
      _ = 1 := by norm_num
  -- 绝对值不等式：1 = |∫_D h| ≤ ∫_D |h|
  have h_abs : 1 ≤ ∫ z in D, |h z| := by
    calc
      (1 : ℝ) = |(1 : ℝ)| := by norm_num
      _ = |∫ z in D, h z| := by rw [h_int_val]
      _ ≤ ∫ z in D, |h z| := abs_integral_le_integral_abs
  -- 注意到 |h z| = |xy - 1| * |f z| = g(z) * |f z|
  have h_abs_eq : ∀ z, |h z| = g z * |f z| := by
    intro z
    unfold h g
    rw [abs_mul]
  -- 将积分中的 |h| 替换为 g * |f|
  have h_abs' : 1 ≤ ∫ z in D, g z * |f z| := by
    simpa [h_abs_eq] using h_abs
  -- 证明 |f| 连续
  have h_absf_cont : Continuous (|f|) := continuous_abs.comp hf_cont
  -- 逐点不等式：∀ z ∈ D, g z * |f z| ≤ (1/b) * g z
  have h_le : ∀ z ∈ D, g z * |f z| ≤ (1 / b) * g z := by
    intro z hz
    have hf_bound : |f z| ≤ 1 / b := le_of_lt (h_bound z hz)
    calc
      g z * |f z| = |f z| * g z := by ring
      _ ≤ (1 / b) * g z := mul_le_mul_of_nonneg_right hf_bound (g_nonneg z)
  -- 转化为几乎处处不等式（在 volume.restrict D 下）
  have h_le_ae : ∀ᵐ z ∂(volume.restrict D), g z * |f z| ≤ (1 / b) * g z := by
    filter_upwards with z hz using h_le z hz
  -- 可积性
  have h_int_fg : IntegrableOn (fun z => g z * |f z|) D :=
    (g_continuous.mul h_absf_cont).continuousOn.integrableOn_compact D_compact
  have h_int_const : IntegrableOn (fun z => (1 / b) * g z) D :=
    (continuous_const.mul g_continuous).continuousOn.integrableOn_compact D_compact
  -- 应用积分单调性
  have h_int_le : ∫ z in D, g z * |f z| ≤ ∫ z in D, (1 / b) * g z :=
    integral_mono_ae h_int_fg h_int_const h_le_ae
  have h_right : ∫ z in D, (1 / b) * g z = 1 := by
    calc
      ∫ z in D, (1 / b) * g z = (1 / b) * ∫ z in D, g z := by
        rw [integral_const_mul]
      _ = (1 / b) * b := by rfl
      _ = 1 := by field_simp [ne_of_gt b_pos]
  rw [h_right] at h_int_le
  -- 现在我们有 1 ≤ ∫_D g * |f| ≤ 1，所以 ∫_D g * |f| = 1
  have h_int_eq : ∫ z in D, g z * |f z| = 1 := by linarith
  -- 严格不等式部分：需要证明 ∫_D g * |f| < 1，矛盾
  -- TODO: 利用 (0,0) 点的严格不等式和连续性，证明存在邻域使得严格不等式成立，
  -- 从而积分严格小于 1。这需要更深入的测度论引理。
  have h_strict_ineq : ∫ z in D, g z * |f z| < 1 := by
    sorry
  linarith
