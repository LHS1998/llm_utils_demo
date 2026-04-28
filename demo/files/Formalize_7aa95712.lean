import Mathlib
open MeasureTheory
open Set
open Real
open Topology
open Filter

-- 矩形区域 D = [0,2] × [0,2]
def D : Set (ℝ × ℝ) := Set.prod (Set.Icc (0 : ℝ) 2) (Set.Icc (0 : ℝ) 2)

-- D 是紧集
lemma D_compact : IsCompact D := by
  exact isCompact_Icc.prod isCompact_Icc

-- D 非空
lemma D_nonempty : D.Nonempty := by
  use (0, 0)
  constructor <;> norm_num

-- D 是可测集
lemma D_meas : MeasurableSet D := by
  exact measurableSet_Icc.prod measurableSet_Icc

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

-- b 为正
lemma b_pos : 0 < b := by
  -- 可积性
  have hgi : IntegrableOn g D :=
    g_continuous.continuousOn.integrableOn_compact D_compact
  have hg_nonneg : 0 ≤ g := g_nonneg
  -- 转换为 restrict 测度
  set μ := volume.restrict D with hμ
  have hgi' : Integrable g μ := hgi
  have h_pos_iff : 0 < ∫ x, g x ∂μ ↔ 0 < μ (Function.support g) :=
    integral_pos_iff_support_of_nonneg hg_nonneg hgi'
  -- 需要证明右边成立
  refine h_pos_iff.2 ?_
  -- 点 p = (0.5, 0.5) ∈ D 使得 g p > 0
  set p : ℝ × ℝ := (0.5, 0.5) with hp_def
  have hp_mem : p ∈ D := by unfold D; constructor <;> norm_num
  have hp_pos : g p > 0 := by unfold g p; norm_num
  -- 由于 p 在 D 内部，存在开集 U ⊆ D 包含 p
  set U : Set (ℝ × ℝ) := Set.Ioo (0 : ℝ) 2 ×ˢ Set.Ioo (0 : ℝ) 2 with hU_def
  have hU_open : IsOpen U := isOpen_Ioo.prod isOpen_Ioo
  have hpU : p ∈ U := by norm_num [U, p]
  have hU_sub : U ⊆ D := by
    intro z hz
    rcases hz with ⟨hz1, hz2⟩
    rcases hz1 with ⟨hx1, hx2⟩
    rcases hz2 with ⟨hy1, hy2⟩
    exact ⟨⟨by linarith, by linarith⟩, ⟨by linarith, by linarith⟩⟩
  -- 由于 g 连续，存在开集 V 使得 p ∈ V 且 ∀ z ∈ V, g z > 0
  have h_cont_at : ContinuousAt g p := g_continuous.continuousAt
  have h_tendsto : Tendsto g (𝓝 p) (𝓝 (g p)) := h_cont_at.tendsto
  have h_eventually : ∀ᶠ z in 𝓝 p, g z > 0 :=
    h_tendsto (lt_mem_nhds hp_pos)
  rcases mem_nhds_iff.1 h_eventually with ⟨V, hV_sub, hV_open, hpV⟩
  -- 取交 W = U ∩ V
  set W := U ∩ V with hW_def
  have hW_open : IsOpen W := hU_open.inter hV_open
  have hpW : p ∈ W := ⟨hpU, hpV⟩
  have hW_nonempty : W.Nonempty := ⟨p, hpW⟩
  have hW_sub_D : W ⊆ D := fun z hz => hU_sub hz.1
  have hW_support : W ⊆ Function.support g := by
    intro z hz
    have hgz : g z > 0 := hV_sub hz.2
    rw [Function.mem_support]
    exact ne_of_gt hgz
  -- volume W > 0（非空开集）
  have hW_meas : MeasurableSet W := hW_open.measurableSet
  have h_vol_pos : 0 < volume W := hW_open.measure_pos volume hW_nonempty
  -- 由于 W ⊆ D，μ W = volume W
  have hμW_eq : μ W = volume W := by
    rw [hμ, Measure.restrict_apply hW_meas, Set.inter_eq_self_of_subset_left hW_sub_D]
  -- 因此 μ (support g) ≥ μ W > 0
  calc
    0 < μ W := by rwa [hμW_eq]
    _ ≤ μ (Function.support g) := measure_mono hW_support

-- 主定理 - 采用最大值方法
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
  -- 由于 D 紧致且 |f| 连续，|f| 在 D 上达到最大值 M
  have h_max : ∃ z₀ ∈ D, IsMaxOn (|f|) D z₀ :=
    D_compact.exists_isMaxOn D_nonempty h_absf_cont.continuousOn
  rcases h_max with ⟨z₀, hz₀, hmax⟩
  set M := |f| z₀ with hM_def
  -- M 是最大值：∀ z ∈ D, |f z| ≤ M
  have hM_le : ∀ z ∈ D, |f z| ≤ M := fun z hz => hmax hz
  -- 由反证假设，M < 1/b
  have hM_lt : M < 1 / b := h_bound z₀ hz₀
  -- 可积性
  have h_int_fg : IntegrableOn (fun z => g z * |f z|) D :=
    (g_continuous.mul h_absf_cont).continuousOn.integrableOn_compact D_compact
  have h_int_gM : IntegrableOn (fun z => M * g z) D :=
    (continuous_const.mul g_continuous).continuousOn.integrableOn_compact D_compact
  -- 逐点不等式：g(z) * |f(z)| ≤ M * g(z)
  have h_le : ∀ z ∈ D, g z * |f z| ≤ M * g z := by
    intro z hz
    have h1 : |f z| ≤ M := hM_le z hz
    have h2 : 0 ≤ g z := g_nonneg z
    calc
      g z * |f z| = |f z| * g z := by ring
      _ ≤ M * g z := mul_le_mul_of_nonneg_right h1 h2
  -- 转化为几乎处处不等式
  have h_mem : ∀ᵐ z ∂(volume.restrict D), z ∈ D := ae_restrict_mem D_meas
  have h_le_ae : ∀ᵐ z ∂(volume.restrict D), g z * |f z| ≤ M * g z := by
    filter_upwards [h_mem] with z hz using h_le z hz
  -- 应用积分单调性
  have h_int_le : ∫ z in D, g z * |f z| ≤ ∫ z in D, M * g z :=
    integral_mono_ae h_int_fg h_int_gM h_le_ae
  -- 计算右边积分
  have h_right : ∫ z in D, M * g z = M * b := by
    calc
      ∫ z in D, M * g z = M * ∫ z in D, g z := by rw [integral_const_mul]
      _ = M * b := by rfl
  rw [h_right] at h_int_le
  -- 现在有 1 ≤ ∫ g*|f| ≤ M*b
  -- 由于 M < 1/b，所以 M*b < (1/b)*b = 1
  have hMb_lt : M * b < 1 := by
    calc
      M * b < (1 / b) * b := mul_lt_mul_of_pos_right hM_lt b_pos
      _ = 1 := by field_simp [ne_of_gt b_pos]
  -- 得到 1 ≤ ∫ g*|f| ≤ M*b < 1，即 1 < 1，矛盾
  linarith
