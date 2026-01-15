import streamlit as st
import sys
import os
import importlib.util
import traceback
import pandas as pd
import biosteam as bst
import matplotlib.pyplot as plt

# --- 1. 页面配置 ---
st.set_page_config(page_title="3HP Biorefinery Enterprise Model", layout="wide", page_icon="🏭")
st.title("🏭 3HP 生物炼制工厂：企业级仿真报告 (最终稳定版)")


# --- 2. 核心加载逻辑 ---
@st.cache_resource
def load_system_core():
    root = os.path.dirname(os.path.abspath(__file__))
    target = "system_light_lle_vacuum_distillation.py"
    sys_path = None
    for dirpath, _, filenames in os.walk(root):
        if target in filenames:
            sys_path = os.path.join(dirpath, target)
            break
    if not sys_path: return None

    keys_to_del = [k for k in sys.modules if 'biorefineries.HP' in k]
    for k in keys_to_del: del sys.modules[k]

    module_name = "biorefineries.HP.systems.system_light_lle_vacuum_distillation"
    spec = importlib.util.spec_from_file_location(module_name, sys_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    # 提取关键对象
    sys_obj = getattr(module, 'HP_sys', None)
    if not sys_obj:
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, bst.System):
                sys_obj = obj
                break
    return sys_obj


# --- 3. 侧边栏 ---
st.sidebar.header("🎛️ 仿真控制参数")
with st.sidebar.expander("🏭 运营参数", expanded=True):
    op_hours = st.sidebar.number_input("年运行时间 (hr)", 6000, 8760, 8000, step=100)
with st.sidebar.expander("💲 市场与原料", expanded=True):
    glucose_price = st.sidebar.number_input("葡萄糖/原料价格 ($/kg)", 0.0, 5.0, 0.40, format="%.3f")
    elec_price = st.sidebar.number_input("工业电价 ($/kWh)", 0.0, 1.0, 0.07, format="%.3f")
with st.sidebar.expander("📈 财务指标", expanded=True):
    tax_rate = st.sidebar.slider("企业所得税率", 0, 50, 35) / 100
    irr_target = st.sidebar.slider("目标内部收益率 (IRR)", 0, 40, 10) / 100

run_btn = st.sidebar.button("🚀 生成深度分析报告", type="primary")

# --- 4. 核心计算逻辑 ---
if run_btn:
    try:
        with st.spinner("正在启动 BioSTEAM 引擎执行全厂物料与能量平衡..."):
            sys_obj = load_system_core()

            # 注入参数
            sys_obj.operating_hours = op_hours
            sys_obj.TEA.income_tax = tax_rate
            sys_obj.TEA.IRR = irr_target
            bst.PowerUtility.price = elec_price

            # 手动注入 GWP 因子 (解决碳足迹为0的关键)
            for feed in sys_obj.feeds:
                if 'glu' in feed.ID.lower() or 'sugar' in feed.ID.lower():
                    feed.price = glucose_price
                    feed.characterization_factors['GWP'] = 0.61  # NREL 标准
                elif 'h2so4' in feed.ID.lower():
                    feed.characterization_factors['GWP'] = 0.12
                elif 'naoh' in feed.ID.lower():
                    feed.characterization_factors['GWP'] = 1.15

            # 执行模拟
            sys_obj.simulate()

            # --- 锁定真正的 3HP 产品流股 ---
            # 排除掉流量巨大的水(Water)，寻找 ID 包含 'HP' 的流股
            main_product = None
            possible_products = [s for s in sys_obj.products if 'HP' in s.ID.upper() and s.F_mass > 0.1]

            if possible_products:
                main_product = sorted(possible_products, key=lambda x: x.F_mass, reverse=True)[0]
            else:
                # 保底逻辑：寻找质量流量在前 5 名且 ID 不含 'water' 的流股
                fallback = [s for s in sys_obj.products if 'water' not in s.ID.lower() and s.F_mass > 1]
                main_product = sorted(fallback, key=lambda x: x.F_mass, reverse=True)[0]

            # 求解 MPSP
            mpsp = sys_obj.TEA.solve_price(main_product)

            # 计算总 GWP
            total_gwp = sum([f.characterization_factors.get('GWP', 0) * f.F_mass for f in sys_obj.feeds])
            gwp = total_gwp / (main_product.F_mass + 1e-6)

        # --- 5. 结果展示 ---
        st.success(f"✅ 核心评估流股已锁定: {main_product.ID}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 MPSP (最低售价)", f"${mpsp:.3f} /kg")
        c2.metric("🌍 GWP (碳排放)", f"{gwp:.3f} kgCO2e/kg")
        c3.metric("🏭 总投资 (TCI)", f"${sys_obj.TEA.TCI / 1e6:.1f} M")

        net_power = sys_obj.power_utility.rate
        p_label = "⚡ 净售电 (CHP)" if net_power < 0 else "⚡ 净耗电"
        c4.metric(p_label, f"{abs(net_power):.1f} kW")

        st.divider()

        t1, t2, t3 = st.tabs(["📊 成本分析", "💸 现金流", "⚙️ 物料验证"])

        with t1:
            col_a, col_b = st.columns(2)
            with col_a:
                st.write("#### 年度运营成本分布")
                try:
                    mat_cost = sys_obj.TEA.material_cost / 1e6
                    util_cost = sys_obj.TEA.utility_cost / 1e6
                    voc = sys_obj.TEA.VOC / 1e6
                    fig, ax = plt.subplots()
                    ax.pie([max(0.1, mat_cost), max(0.1, util_cost), max(0.1, voc - mat_cost - util_cost)],
                           labels=['Materials', 'Utilities', 'Fixed'], autopct='%1.1f%%',
                           colors=['#ff9999', '#66b3ff', '#99ff99'])
                    st.pyplot(fig)
                except:
                    st.warning("成本构成解析失败")
            with col_b:
                h_duty = sum([hu.duty for u in sys_obj.units for hu in u.heat_utilities if hu.duty > 0]) / 1e6
                st.info(f"🔥 累计加热负荷: {h_duty:.2f} MM kJ/hr")

        with t2:
            df_cash = sys_obj.TEA.get_cashflow_table()
            st.dataframe(pd.DataFrame(df_cash.values, index=df_cash.index, columns=df_cash.columns), width='stretch')

        with t3:
            # 彻底修复物料表格
            chems = main_product.chemicals
            df_mass = pd.DataFrame({
                "Chemical": chems.IDs,
                "Mass Flow (kg/hr)": list(main_product.mass)
            })
            st.dataframe(df_mass[df_mass["Mass Flow (kg/hr)"] > 0.001].reset_index(drop=True), width='stretch')

    except Exception as e:
        st.error(f"分析失败: {str(e)}")
        st.code(traceback.format_exc())
else:
    st.info("👈 请点击按钮启动模拟，生成由底层物理逻辑驱动的完整报告。")