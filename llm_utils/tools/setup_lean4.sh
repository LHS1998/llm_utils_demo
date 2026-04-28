#!/bin/bash
# LEAN4 + mathlib 环境配置脚本
# 用于在 llm_utils/tools/lean4_project/ 下创建 LEAN4 项目并配置 mathlib 依赖

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}/lean4_project"

echo "=========================================="
echo "  LEAN4 + mathlib 环境配置脚本"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. 检查并安装 elan
check_and_install_elan() {
    info "检查 elan（LEAN 工具链管理器）..."
    
    if command -v elan &> /dev/null; then
        info "elan 已安装: $(elan --version)"
        return 0
    fi
    
    warn "elan 未安装，正在安装..."
    
    # 使用官方安装脚本安装 elan
    curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -s -- -y --default-toolchain none
    
    # 加载 elan 环境
    export PATH="$HOME/.elan/bin:$PATH"
    
    if command -v elan &> /dev/null; then
        info "elan 安装成功: $(elan --version)"
    else
        error "elan 安装失败，请手动安装: https://github.com/leanprover/elan"
        exit 1
    fi
}

# 2. 检查 lake 命令
check_lake() {
    info "检查 lake（LEAN 构建系统）..."
    
    if command -v lake &> /dev/null; then
        info "lake 已可用: $(lake --version 2>/dev/null || echo '版本未知')"
        return 0
    fi
    
    # lake 通常随 lean4 工具链一起安装
    warn "lake 未找到，将在初始化项目时自动安装..."
}

# 3. 创建项目目录结构
create_project_structure() {
    info "创建项目目录结构: ${PROJECT_DIR}"
    
    # 创建项目目录
    mkdir -p "${PROJECT_DIR}/Scratch"
    
    # 创建 .gitkeep 文件
    touch "${PROJECT_DIR}/Scratch/.gitkeep"
    
    info "目录结构创建完成"
}

# 4. 创建临时 lean-toolchain 文件（后续会被 mathlib 的版本覆盖）
create_toolchain_file() {
    local TOOLCHAIN_FILE="${PROJECT_DIR}/lean-toolchain"
    
    info "创建临时 lean-toolchain 文件..."
    
    # 创建一个临时的 toolchain 文件，使用一个常见的稳定版本
    # 这个文件会在 lake update 后被 mathlib 的实际版本覆盖
    cat > "${TOOLCHAIN_FILE}" << 'EOF'
leanprover/lean4:v4.27.0-rc1
EOF
    
    info "临时 lean-toolchain 文件创建完成"
}

# 4.5 同步 mathlib 的 toolchain 版本
sync_toolchain() {
    local TOOLCHAIN_FILE="${PROJECT_DIR}/lean-toolchain"
    local MATHLIB_TOOLCHAIN="${PROJECT_DIR}/.lake/packages/mathlib/lean-toolchain"
    
    info "同步 mathlib 的 toolchain 版本..."
    
    if [ -f "${MATHLIB_TOOLCHAIN}" ]; then
        cp "${MATHLIB_TOOLCHAIN}" "${TOOLCHAIN_FILE}"
        info "已同步 toolchain 版本: $(cat ${TOOLCHAIN_FILE})"
    else
        warn "未找到 mathlib 的 toolchain 文件，使用默认版本"
    fi
}

# 5. 创建 lakefile.toml
create_lakefile() {
    local LAKEFILE="${PROJECT_DIR}/lakefile.toml"
    
    info "创建 lakefile.toml..."
    
    cat > "${LAKEFILE}" << 'EOF'
name = "lean4_project"
version = "0.1.0"
defaultTargets = ["Scratch"]

[[require]]
name = "mathlib"
scope = "leanprover-community"
rev = "master"

[[lean_lib]]
name = "Scratch"
globs = ["Scratch"]
EOF
    
    info "lakefile.toml 创建完成"
}

# 6. 创建示例文件
create_example_file() {
    local EXAMPLE_FILE="${PROJECT_DIR}/Scratch/Example.lean"
    
    info "创建示例文件 Scratch/Example.lean..."
    
    cat > "${EXAMPLE_FILE}" << 'EOF'
-- LEAN4 示例文件
-- 此文件用于验证环境配置是否正确

import Mathlib.Tactic

-- 简单的证明示例
example : 1 + 1 = 2 := by norm_num

-- 使用 ring 策略
example (a b : ℤ) : (a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2 := by ring

-- 逻辑证明
example (p q : Prop) (hp : p) (hq : q) : p ∧ q := by
  constructor
  · exact hp
  · exact hq

#check Nat.add_comm
EOF
    
    info "示例文件创建完成"
}

# 7. 初始化项目依赖
init_project() {
    info "初始化项目依赖（这可能需要几分钟）..."
    
    cd "${PROJECT_DIR}"
    
    # 更新依赖
    info "运行 lake update..."
    lake update
    
    info "依赖初始化完成"
}

# 7.5 下载 mathlib 预编译缓存
download_mathlib_cache() {
    info "下载 mathlib 预编译缓存（这可能需要几分钟，取决于网络速度）..."
    
    cd "${PROJECT_DIR}"
    
    # 使用 lake exe cache get 下载预编译的 mathlib
    # 这比从源码编译快得多
    if lake exe cache get 2>&1; then
        info "mathlib 缓存下载成功！"
    else
        warn "mathlib 缓存下载失败"
        warn "你可以稍后手动运行 'cd ${PROJECT_DIR} && lake exe cache get' 来重试"
        warn "或者运行 'lake build' 从源码编译（需要较长时间）"
    fi
}

# 8. 构建项目（可选，用于验证）
build_project() {
    info "构建项目以验证配置..."
    
    cd "${PROJECT_DIR}"
    
    # 构建示例文件
    if lake build Scratch 2>&1; then
        info "项目构建成功！"
    else
        warn "项目构建失败，但这可能是正常的（首次构建可能需要下载更多依赖）"
        warn "你可以稍后手动运行 'cd ${PROJECT_DIR} && lake build' 来重试"
    fi
}

# 9. 验证安装
verify_installation() {
    info "验证安装..."
    
    cd "${PROJECT_DIR}"
    
    # 检查 lean 是否可以运行
    if lake env lean --version &> /dev/null; then
        info "LEAN4 版本: $(lake env lean --version)"
    else
        warn "无法获取 LEAN4 版本信息"
    fi
    
    # 检查示例文件
    info "检查示例文件..."
    if lake env lean Scratch/Example.lean 2>&1 | grep -q "error"; then
        warn "示例文件有错误，请检查配置"
    else
        info "示例文件检查通过"
    fi
}

# 主流程
main() {
    # 检查是否已经初始化
    if [ -f "${PROJECT_DIR}/lake-manifest.json" ]; then
        warn "项目已初始化，如需重新初始化请先删除 ${PROJECT_DIR}"
        read -p "是否继续更新依赖？[y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "已取消"
            exit 0
        fi
    fi
    
    # 执行安装步骤
    check_and_install_elan
    check_lake
    create_project_structure
    create_toolchain_file
    create_lakefile
    create_example_file
    init_project
    sync_toolchain
    download_mathlib_cache
    
    # 询问是否构建
    read -p "是否立即构建项目以验证配置？（可能需要较长时间）[y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        build_project
    fi
    
    verify_installation
    
    echo ""
    echo "=========================================="
    info "LEAN4 + mathlib 环境配置完成！"
    echo "=========================================="
    echo ""
    echo "项目位置: ${PROJECT_DIR}"
    echo ""
    echo "使用方法:"
    echo "  cd ${PROJECT_DIR}"
    echo "  lake env lean Scratch/YourFile.lean  # 检查 Lean 文件"
    echo "  lake build                           # 构建项目"
    echo ""
    echo "在 Python 中使用:"
    echo "  from llm_utils.tools import create_executors, LEAN4"
    echo "  executors = create_executors(LEAN4)"
    echo "  result = executors[LEAN4].execute('example : 1 + 1 = 2 := by norm_num')"
    echo ""
}

# 运行主流程
main "$@"
