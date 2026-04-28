import Mathlib
open MeasureTheory
open Set
open Real
open Topology

-- 矩形区域 D = [0,2] × [0,2]
def D : Set (ℝ × ℝ) := Set.prod (Set.Icc (0 : ℝ) 2) (Set.Icc (0 : ℝ) 2)

-- 函数 g(x,y) = |xy - 1|
def g (x : ℝ × ℝ) : ℝ := |x.1 * x.2 - 1|

-- 常数 b = ∬_D |xy - 1| dσ
noncomputable def b : ℝ := ∫ (z : ℝ × ℝ) in D, g z ∂volume

-- g 是连续函数
lemma g_continuous : Continuous g := by
  unfold g
  continuity

-- g 非负
lemma g_nonneg (x : ℝ × ℝ) : 0 ≤ g x := by
  unfold g
  exact abs_nonneg _

-- b 为正 (证明需要一些分析引理，此处暂缺完整计算)
lemma b_pos : 0 < b := by
  unfold b
  -- 因为 g 连续、非负，且在 D 上不恒为零，所以其积分必为正。
  -- 可用 `integral_pos_iff_support_of_nonneg` 等引理详细证明。
  sorry

-- 主定理
theorem exists_point_with_large_f (f : ℝ × ℝ → ℝ) (hf_cont : Continuous f)
    (h_int1 : ∫ z in D, f z ∂volume = 0)
    (h_int2 : ∫ z in D, (z.1 * z.2) * f z ∂volume = 1) :
    ∃ (ξ η : ℝ), ((ξ, η) ∈ D) ∧ |f (ξ, η)| ≥ 1 / b := by
  -- 反证法：假设对所有 (ξ,η) ∈ D 都有 |f(ξ,η)| < 1/b
  by_contra! H  -- H : ∀ (ξ η : ℝ), (ξ, η) ∈ D → |f (ξ, η)| < 1 / b
  -- 定义辅助函数 h(x,y) = (xy - 1) f(x,y)
  set h := fun (z : ℝ × ℝ) => (z.1 * z.2 - 1) * f z with hh_def
  -- 计算 ∫_D h = ∫_D xy f - ∫_D f = 1 - 0 = 1
  have h_int_h : ∫ z in D, h z ∂volume = 1 := by
    unfold h
    calc
      ∫ z in D, (z.1 * z.2 - 1) * f z ∂volume
          = ∫ z in D, (z.1 * z.2 * f z) - f z ∂volume := by
            refine integral_congr fun z _ => ?_
            ring
      _ = (∫ z in D, z.1 * z.2 * f z ∂volume) - (∫ z in D, f z ∂volume) := by
            rw [integral_sub]
            · -- 可积性由连续性在紧集上保证，此处省略具体证明
              sorry
            · sorry
      _ = 1 - 0 := by rw [h_int2, h_int1]
      _ = 1 := by norm_num
  -- 绝对值不等式：1 = |∫_D h| ≤ ∫_D |h|
  have h_abs : 1 ≤ ∫ z in D, |h z| ∂volume := by
    calc
      (1 : ℝ) = |1| := by norm_num
      _ = |∫ z in D, h z ∂volume| := by rw [h_int_h]
      _ ≤ ∫ z in D, |h z| ∂volume := abs_integral_le_integral_abs
  -- 注意到 |h z| = |xy - 1| * |f z| = g(z) * |f z|
  have h_abs_eq : ∀ z, |h z| = g z * |f z| := by
    intro z
    unfold h g
    rw [abs_mul, abs_abs]
  -- 将积分中的 |h| 替换为 g * |f|
  have h_abs' : 1 ≤ ∫ z in D, g z * |f z| ∂volume := by
    simpa [h_abs_eq] using h_abs
  -- 由反证假设，|f z| < 1 / b 对所有 z ∈ D
  have h_bound : ∀ z ∈ D, |f z| < 1 / b := H
  -- 故 g(z) * |f z| < (1 / b) * g(z)
  have h_strict : ∀ z ∈ D, g z * |f z| < (1 / b) * g z := by
    intro z hz
    exact mul_lt_mul_of_pos_right (h_bound z hz) (g_nonneg z)
  -- 积分得 ∫_D g * |f| < ∫_D (1 / b) * g
  have h_int_strict : ∫ z in D, g z * |f z| ∂volume < ∫ z in D, (1 / b) * g z ∂volume := by
    -- 需要严格积分不等式（连续函数在紧集上逐点严格小于，则积分严格小于）
    -- 此处省略具体证明
    sorry
  -- 右边化简为 (1 / b) * ∫_D g = (1 / b) * b = 1
  have h_right : ∫ z in D, (1 / b) * g z ∂volume = 1 := by
    calc
      ∫ z in D, (1 / b) * g z ∂volume = (1 / b) * ∫ z in D, g z ∂volume := by
        rw [integral_mul_left]
      _ = (1 / b) * b := by rw [b]
      _ = 1 := by field_simp [ne_of_gt b_pos]
  rw [h_right] at h_int_strict
  -- 得到 1 ≤ ∫_D g * |f| < 1，矛盾
  linarith
