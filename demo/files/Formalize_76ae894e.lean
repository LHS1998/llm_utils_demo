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

-- D 的体积为 4
lemma volume_D : volume D = 4 := by
  calc
    volume D = volume (Set.Icc (0 : ℝ) 2) * volume (Set.Icc (0 : ℝ) 2) := by
      rw [volume_prod]
    _ = (ENNReal.ofReal (2 - 0)) * (ENNReal.ofReal (2 - 0)) := by simp
    _ = (ENNReal.ofReal 2) * (ENNReal.ofReal 2) := by norm_num
    _ = ENNReal.ofReal 4 := by norm_num
    _ = (4 : ℝ≥0∞) := by norm_num

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
noncomputable def b : ℝ := ∫ (z : ℝ × ℝ) in D, g z ∂volume

-- b 为正（暂时用 sorry 跳过证明）
lemma b_pos : 0 < b := by
  sorry

-- 主定理
theorem exists_point_with_large_f (f : ℝ × ℝ → ℝ) (hf_cont : Continuous f)
    (h_int1 : ∫ z in D, f z ∂volume = 0)
    (h_int2 : ∫ z in D, (z.1 * z.2) * f z ∂volume = 1) :
    ∃ (ξ η : ℝ), ((ξ, η) ∈ D) ∧ |f (ξ, η)| ≥ 1 / b := by
  -- 反证法：假设对所有 (ξ,η) ∈ D 都有 |f(ξ,η)| < 1/b
  by_contra! H  -- H : ∀ (ξ η : ℝ), (ξ, η) ∈ D → |f (ξ, η)| < 1 / b
  -- 将 H 转换为 ∀ z ∈ D, |f z| < 1 / b
  have h_bound : ∀ z ∈ D, |f z| < 1 / b := by
    intro z hz
    rcases z with ⟨ξ, η⟩
    exact H ξ η hz
  -- 定义辅助函数 h(x,y) = (xy - 1) f(x,y)
  set h := fun (z : ℝ × ℝ) => (z.1 * z.2 - 1) * f z with hh_def
  -- 证明 h 在 D 上可积
  have h_int_h : IntegrableOn h D volume := by
    unfold h
    refine Continuous.integrableOn_compact D_compact ?_
    continuity
  -- 计算 ∫_D h = ∫_D xy f - ∫_D f = 1 - 0 = 1
  have h_int_val : ∫ z in D, h z ∂volume = 1 := by
    unfold h
    calc
      ∫ z in D, (z.1 * z.2 - 1) * f z ∂volume = ∫ z in D, (z.1 * z.2 * f z - f z) ∂volume := by
        refine integral_congr_ae ?_
        refine ae_of_all (volume.restrict D) fun z => ?_
        ring
      _ = (∫ z in D, z.1 * z.2 * f z ∂volume) - (∫ z in D, f z ∂volume) := by
        rw [integral_sub]
        · exact Continuous.integrableOn_compact D_compact (by continuity)
        · exact hf_cont.integrableOn_compact D_compact
      _ = 1 - 0 := by rw [h_int2, h_int1]
      _ = 1 := by norm_num
  -- 绝对值不等式：1 = |∫_D h| ≤ ∫_D |h|
  have h_abs : 1 ≤ ∫ z in D, |h z| ∂volume := by
    calc
      (1 : ℝ) = |1| := by norm_num
      _ = |∫ z in D, h z ∂volume| := by rw [h_int_val]
      _ ≤ ∫ z in D, |h z| ∂volume := abs_integral_le_integral_abs _
  -- 注意到 |h z| = |xy - 1| * |f z| = g(z) * |f z|
  have h_abs_eq : ∀ z, |h z| = g z * |f z| := by
    intro z
    unfold h g
    rw [abs_mul (z.1 * z.2 - 1) (f z)]
  -- 将积分中的 |h| 替换为 g * |f|
  have h_abs' : 1 ≤ ∫ z in D, g z * |f z| ∂volume := by
    simpa [h_abs_eq] using h_abs
  -- 证明 |f| 连续
  have h_absf_cont : Continuous (|f|) := continuous_abs.comp hf_cont
  -- 证明 g * |f| 和 (1/b) * g 在 D 上连续
  have h_cont1 : ContinuousOn (fun z => g z * |f z|) D := by
    exact (g_continuous.mul h_absf_cont).continuousOn
  have h_cont2 : ContinuousOn (fun z => (1 / b) * g z) D := by
    exact (continuous_const.mul g_continuous).continuousOn
  -- 逐点不等式：∀ z ∈ D, g z * |f z| ≤ (1/b) * g z
  have h_le : ∀ z ∈ D, g z * |f z| ≤ (1 / b) * g z := by
    intro z hz
    have hf_bound : |f z| ≤ 1 / b := le_of_lt (h_bound z hz)
    calc
      g z * |f z| = |f z| * g z := by ring
      _ ≤ (1 / b) * g z := mul_le_mul_of_nonneg_right hf_bound (g_nonneg z)
  -- 存在点使得严格不等式成立：取 (0,0) ∈ D
  have h_strict : ∃ z ∈ D, g z * |f z| < (1 / b) * g z := by
    use (0, 0)
    constructor
    · unfold D
      constructor <;> constructor <;> norm_num
    · unfold g
      have hf0 : |f (0, 0)| < 1 / b := h_bound (0, 0) (by unfold D; constructor <;> constructor <;> norm_num)
      calc
        |(0 : ℝ) * (0 : ℝ) - 1| * |f (0, 0)| = 1 * |f (0, 0)| := by norm_num
        _ = |f (0, 0)| := by ring
        _ < 1 / b := hf0
        _ = (1 / b) * 1 := by ring
        _ = (1 / b) * |(0 : ℝ) * (0 : ℝ) - 1| := by norm_num
  -- 应用积分严格不等式引理
  have h_int_lt : ∫ z in D, g z * |f z| ∂volume < ∫ z in D, (1 / b) * g z ∂volume := by
    refine ContinuousOn.integral_lt_integral_of_continuousOn_of_le_of_exists_lt D_compact h_cont1 h_cont2 ?_ h_strict
    intro z hz
    exact h_le z hz
  -- 计算右边积分：∫_D (1/b) * g = (1/b) * ∫_D g = (1/b) * b = 1
  have h_right : ∫ z in D, (1 / b) * g z ∂volume = 1 := by
    calc
      ∫ z in D, (1 / b) * g z ∂volume = (1 / b) * ∫ z in D, g z ∂volume := by
        rw [integral_const_mul]
      _ = (1 / b) * b := by rfl
      _ = 1 := by field_simp [ne_of_gt b_pos]
  rw [h_right] at h_int_lt
  -- 得到 1 ≤ ∫_D g * |f| < 1，矛盾
  linarith
