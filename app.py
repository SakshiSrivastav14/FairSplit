import streamlit as st
import matplotlib.pyplot as plt
import random
import time
import statistics
import csv
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER
import database as db


st.markdown("<style>span{font-weight:bold;}</style>", unsafe_allow_html=True)

st.markdown("""
    <style>
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 8px 16px;
    }
    .stProgress > div > div {
        background-color: #4CAF50;
    }
    .stAlert {
        background-color: #2A2A2A !important;
        color: white !important;
        border-left: 5px solid #4CAF50 !important;
    }
    </style>
""", unsafe_allow_html=True)

st.set_page_config(
    page_title="FairSplit - Transparent Group Payments",
    page_icon="",
    layout="centered"
)

def apply_custom_styling():
    st.markdown("""
        <style>
        .main {
            background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
        }
        .stButton>button {
            width: 100%;
            border-radius: 8px;
            font-weight: 600;
        }
        h1 {
            text-align: center;
            color: #2c3e50;
        }
        h3 {
            text-align: center;
            color: #7f8c8d;
            font-weight: 400;
            font-size: 1.1rem;
        }
        .footer {
            text-align: center;
            color: #95a5a6;
            font-size: 0.9rem;
            margin-top: 3rem;
            padding: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)

def initialize_session_state():
    if 'members' not in st.session_state:
        st.session_state.members = []
    if 'fairness_calculated' not in st.session_state:
        st.session_state.fairness_calculated = False
    if 'fairness_data' not in st.session_state:
        st.session_state.fairness_data = None
    if 'expenses' not in st.session_state:
        st.session_state.expenses = []
    if 'current_expense_category' not in st.session_state:
        st.session_state.current_expense_category = "General"

def generate_transaction_id():
    hex_chars = '0123456789ABCDEF'
    return 'SOL_' + ''.join(random.choice(hex_chars) for _ in range(10))

def calculate_fairness(members):
    if not members or len(members) == 0:
        return None
    
    contributions = [m['amount'] for m in members]
    avg_contribution = statistics.mean(contributions)
    
    fairness_details = []
    for member in members:
        difference = member['amount'] - avg_contribution
        fairness_details.append({
            'name': member['name'],
            'amount': member['amount'],
            'currency': member.get('currency', '$'),
            'difference': difference
        })
    
    if len(contributions) > 1:
        std_dev = statistics.stdev(contributions)
    else:
        std_dev = 0
    
    fairness_score = max(0, min(100, 100 - (std_dev * 10)))
    
    return {
        'score': fairness_score,
        'avg_contribution': avg_contribution,
        'details': fairness_details,
        'std_dev': std_dev
    }

def calculate_settlements(members):
    if not members or len(members) == 0:
        return []
    
    total = sum(m['amount'] for m in members)
    fair_share = total / len(members)
    
    balances = []
    for member in members:
        balance = member['amount'] - fair_share
        balances.append({
            'name': member['name'],
            'balance': balance,
            'currency': member.get('currency', '$')
        })
    
    creditors = [b for b in balances if b['balance'] > 0.01]
    debtors = [b for b in balances if b['balance'] < -0.01]
    
    creditors.sort(key=lambda x: x['balance'], reverse=True)
    debtors.sort(key=lambda x: x['balance'])
    
    settlements = []
    i, j = 0, 0
    
    while i < len(creditors) and j < len(debtors):
        creditor = creditors[i]
        debtor = debtors[j]
        
        amount = min(creditor['balance'], -debtor['balance'])
        
        if amount > 0.01:
            settlements.append({
                'from': debtor['name'],
                'to': creditor['name'],
                'amount': amount,
                'currency': creditor.get('currency', '$')
            })
        
        creditor['balance'] -= amount
        debtor['balance'] += amount
        
        if creditor['balance'] < 0.01:
            i += 1
        if debtor['balance'] > -0.01:
            j += 1
    
    return settlements

def generate_ai_explanation(fairness_data):
    score = fairness_data['score']
    details = fairness_data['details']
    
    if len(details) == 0:
        return "No members to analyze."
    
    max_contributor = max(details, key=lambda x: x['amount'])
    min_contributor = min(details, key=lambda x: x['amount'])
    
    if score >= 85:
        fairness_level = "excellent"
        balance_note = "All members contributed nearly equally."
    elif score >= 70:
        fairness_level = "good"
        balance_note = f"{max_contributor['name']} contributed slightly more, while others are balanced."
    elif score >= 50:
        fairness_level = "moderate"
        balance_note = f"There's some imbalance - {max_contributor['name']} paid more than {min_contributor['name']}."
    else:
        fairness_level = "low"
        balance_note = f"Significant imbalance detected between {max_contributor['name']} and {min_contributor['name']}."
    
    return f"According to the fairness model (Llama simulated), {balance_note} Overall fairness is {fairness_level} at {score:.0f}%."

def generate_csv_export(members, fairness_data, settlements):
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['FairSplit - Payment Summary'])
    writer.writerow(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    writer.writerow([])
    
    writer.writerow(['Member Contributions'])
    writer.writerow(['Name', 'Amount Contributed'])
    for member in members:
        writer.writerow([member['name'], f"${member['amount']:.2f}"])
    
    total = sum(m['amount'] for m in members)
    writer.writerow(['Total', f"${total:.2f}"])
    writer.writerow([])
    
    if fairness_data:
        writer.writerow(['Fairness Analysis'])
        writer.writerow(['Fairness Score', f"{fairness_data['score']:.0f}%"])
        writer.writerow(['Average Contribution', f"${fairness_data['avg_contribution']:.2f}"])
        writer.writerow([])
        
        writer.writerow(['Member', 'Paid', 'Difference from Average'])
        for detail in fairness_data['details']:
            diff = detail['difference']
            diff_text = f"+${abs(diff):.2f}" if diff > 0 else f"-${abs(diff):.2f}" if diff < 0 else "$0.00"
            writer.writerow([detail['name'], f"${detail['amount']:.2f}", diff_text])
        writer.writerow([])
    
    if settlements:
        writer.writerow(['Settlement Suggestions'])
        writer.writerow(['From', 'To', 'Amount'])
        for settlement in settlements:
            writer.writerow([settlement['from'], settlement['to'], f"${settlement['amount']:.2f}"])
    else:
        writer.writerow(['Settlement Suggestions'])
        writer.writerow(['No settlements needed - everyone contributed their fair share!'])
    
    return output.getvalue()

def generate_pdf_export(members, fairness_data, settlements):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=8,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=10,
        spaceBefore=12
    )
    
    story.append(Paragraph("FairSplit - Payment Summary", title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Member Contributions", heading_style))
    
    contrib_data = [['Name', 'Amount Contributed']]
    for member in members:
        contrib_data.append([member['name'], f"${member['amount']:.2f}"])
    
    total = sum(m['amount'] for m in members)
    contrib_data.append(['Total', f"${total:.2f}"])
    
    contrib_table = Table(contrib_data, colWidths=[3*inch, 2*inch])
    contrib_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8ecf1')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7'))
    ]))
    story.append(contrib_table)
    story.append(Spacer(1, 0.3*inch))
    
    if fairness_data:
        story.append(Paragraph("Fairness Analysis", heading_style))
        
        score_color = colors.HexColor('#28a745') if fairness_data['score'] >= 70 else colors.HexColor('#dc3545')
        
        fairness_info = [
            ['Fairness Score', f"{fairness_data['score']:.0f}%"],
            ['Average Contribution', f"${fairness_data['avg_contribution']:.2f}"]
        ]
        
        fairness_table = Table(fairness_info, colWidths=[3*inch, 2*inch])
        fairness_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f7fa')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (1, 0), (1, 0), 14),
            ('TEXTCOLOR', (1, 0), (1, 0), score_color),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
        ]))
        story.append(fairness_table)
        story.append(Spacer(1, 0.2*inch))
        
        detail_data = [['Member', 'Paid', 'Difference from Average']]
        for detail in fairness_data['details']:
            diff = detail['difference']
            diff_text = f"+${abs(diff):.2f}" if diff > 0 else f"-${abs(diff):.2f}" if diff < 0 else "$0.00"
            detail_data.append([detail['name'], f"${detail['amount']:.2f}", diff_text])
        
        detail_table = Table(detail_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
        detail_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7'))
        ]))
        story.append(detail_table)
        story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Settlement Suggestions", heading_style))
    
    if settlements:
        settlement_data = [['From', 'To', 'Amount']]
        for settlement in settlements:
            settlement_data.append([settlement['from'], settlement['to'], f"${settlement['amount']:.2f}"])
        
        settlement_table = Table(settlement_data, colWidths=[2*inch, 2*inch, 1.5*inch])
        settlement_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7'))
        ]))
        story.append(settlement_table)
    else:
        story.append(Paragraph("No settlements needed - everyone contributed their fair share!", styles['Normal']))
    
    story.append(Spacer(1, 0.5*inch))
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#95a5a6'),
        alignment=TA_CENTER
    )
    story.append(Paragraph("Powered by FairSplit - Transparent Group Payments", footer_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def render_visualization(members):
    if not members:
        return
    
    names = [m['name'] for m in members]
    amounts = [m['amount'] for m in members]
    
    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6']
    
    bars = ax.bar(names, amounts, color=colors[:len(names)], alpha=0.8, edgecolor='black', linewidth=1.2)
    
    ax.set_xlabel('Members', fontsize=12, fontweight='bold')
    ax.set_ylabel('Amount Contributed ($)', fontsize=12, fontweight='bold')
    ax.set_title('Contribution Comparison', fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'${height:.2f}',
                ha='center', va='bottom', fontweight='bold', fontsize=10)
    
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

def main():
    apply_custom_styling()
    initialize_session_state()
    
    
    st.sidebar.markdown("### FairSplit")
    st.sidebar.markdown("---")
    st.sidebar.info("Add members and their contributions to calculate group payment fairness.")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Payment History")
    
    try:
        saved_groups = db.get_all_groups()
        
        if saved_groups:
            st.sidebar.write(f"**{len(saved_groups)} saved group(s)**")
            
            for group in saved_groups[:10]:
                with st.sidebar.expander(f" {group['name']}", expanded=False):
                    st.write(f"**Category:** {group['category'] or 'General'}")
                    st.write(f"**Total:** ${group['total_amount']:.2f}")
                    st.write(f"**Fairness:** {group['fairness_score']:.0f}%")
                    st.write(f"**Date:** {group['created_at'].strftime('%Y-%m-%d')}")
                    
                    col_load, col_del = st.columns(2)
                    with col_load:
                        if st.button("Load", key=f"load_{group['id']}"):
                            loaded_group = db.get_group_by_id(group['id'])
                            if loaded_group:
                                st.session_state.members = loaded_group['members']
                                st.session_state.fairness_calculated = False
                                st.session_state.fairness_data = None
                                st.success(f"Loaded '{group['name']}'")
                                st.rerun()
                    
                    with col_del:
                        if st.button("Delete", key=f"del_{group['id']}"):
                            try:
                                db.delete_group(group['id'])
                                st.success("Deleted!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {str(e)}")
            
            if len(saved_groups) > 10:
                st.sidebar.info(f"Showing 10 of {len(saved_groups)} groups")
        else:
            st.sidebar.write("No saved groups yet.")
    except Exception as e:
        st.sidebar.error(f"Failed to load history: {str(e)}")
    
    st.markdown("# FairSplit — Transparent Group Payments")
    st.markdown("### Ensuring fairness and trust in every shared expense.")
    st.markdown("---")
    
    st.subheader("Group Members")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        member_name = st.text_input("Member Name", placeholder="e.g., Alice")
    with col2:
        member_amount = st.number_input("Amount Contributed ($)", min_value=0.0, step=0.01, format="%.2f")
    
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button(" Add Member", type="primary"):
            if member_name.strip() and member_amount > 0:
                st.session_state.members.append({
                    'name': member_name.strip(),
                    'amount': member_amount
                })
                st.success(f" Added {member_name} with ${member_amount:.2f}")
                st.session_state.fairness_calculated = False
            else:
                st.error("Please enter a valid name and amount.")
    
    with col_b:
        if st.button(" Clear All"):
            st.session_state.members = []
            st.session_state.expenses = []
            st.session_state.fairness_calculated = False
            st.session_state.fairness_data = None
            st.info("All members and expenses cleared.")
    
    if st.session_state.members:
        st.markdown("#### Current Members:")
        for idx, member in enumerate(st.session_state.members):
            col_name, col_amt, col_del = st.columns([3, 2, 1])
            with col_name:
                st.text(f"{idx + 1}. {member['name']}")
            with col_amt:
                st.text(f"${member['amount']:.2f}")
            with col_del:
                if st.button("cancel", key=f"del_{idx}"):
                    st.session_state.members.pop(idx)
                    st.session_state.fairness_calculated = False
                    st.rerun()
    
    st.markdown("---")
    
    st.markdown("###  Expense Categories")
    
    if st.session_state.members:
        col_cat1, col_cat2 = st.columns([2, 1])
        with col_cat1:
            expense_category = st.selectbox("Category for Current Expense", 
                ["General", "Food", "Lodging", "Transportation", "Entertainment", "Bills", "Other"], 
                key="expense_category_selector")
        
        with col_cat2:
            if st.button("Save as Expense Category"):
                if st.session_state.members:
                    st.session_state.expenses.append({
                        'category': expense_category,
                        'members': st.session_state.members.copy()
                    })
                    st.success(f"Added {expense_category} expense")
                    st.session_state.members = []
                    st.session_state.fairness_calculated = False
                    st.rerun()
                else:
                    st.error("No members to save")
    
    if st.session_state.expenses:
        st.markdown("#### Saved Expense Categories:")
        for idx, expense in enumerate(st.session_state.expenses):
            total = sum(m['amount'] for m in expense['members'])
            col_exp, col_rem = st.columns([4, 1])
            with col_exp:
                st.write(f"**{idx + 1}. {expense['category']}** - ${total:.2f} ({len(expense['members'])} members)")
            with col_rem:
                if st.button("", key=f"remove_exp_{idx}"):
                    st.session_state.expenses.pop(idx)
                    st.session_state.fairness_calculated = False
                    st.session_state.fairness_data = None
                    st.rerun()
    
    if not st.session_state.members and not st.session_state.expenses:
        st.info("Add members above and optionally save them as expense categories to track multiple types of expenses.")
    
    st.markdown("---")
    
    all_members_combined = []
    if st.session_state.expenses or st.session_state.members:
        member_totals = {}
        
        for expense in st.session_state.expenses:
            for member in expense['members']:
                if member['name'] not in member_totals:
                    member_totals[member['name']] = 0
                member_totals[member['name']] += member['amount']
        
        for member in st.session_state.members:
            if member['name'] not in member_totals:
                member_totals[member['name']] = 0
            member_totals[member['name']] += member['amount']
        
        if member_totals:
            all_members_combined = [{'name': name, 'amount': amount} for name, amount in member_totals.items()]
    
    if (st.session_state.members and len(st.session_state.members) >= 2) or len(all_members_combined) >= 2:
        calc_label = "Calculate Fairness (All Categories)" if st.session_state.expenses else "Calculate Fairness"
        
        if st.session_state.expenses or st.session_state.members:
            num_categories = len(st.session_state.expenses)
            num_current = len(st.session_state.members)
            num_unique_members = len(all_members_combined)
            
            summary_parts = []
            if num_categories > 0:
                summary_parts.append(f"{num_categories} saved categor{'y' if num_categories == 1 else 'ies'}")
            if num_current > 0:
                summary_parts.append(f"{num_current} current member{'s' if num_current != 1 else ''}")
            
            if summary_parts:
                st.info(f" Ready to analyze: {' + '.join(summary_parts)} = {num_unique_members} unique member{'s' if num_unique_members != 1 else ''}")
        
        if st.button(calc_label, type="primary"):
            with st.spinner("Analyzing fairness using AI..."):
                time.sleep(1.5)
                members_to_analyze = all_members_combined if all_members_combined else st.session_state.members
                fairness_data = calculate_fairness(members_to_analyze)
                st.session_state.fairness_data = fairness_data
                st.session_state.fairness_calculated = True
    
    if st.session_state.fairness_calculated and st.session_state.fairness_data:
        fairness_data = st.session_state.fairness_data
        score = fairness_data['score']
        
        st.markdown("### Fairness Analysis")
        
        if score >= 70:
            box_color = "#d4edda"
            border_color = "#28a745"
            
            status = "Fair Distribution"
        else:
            box_color = "#f8d7da"
            border_color = "#dc3545"
            
            status = "Unbalanced Distribution"
        
        st.markdown(f"""
            <div style="
                background-color: {box_color};
                border: 2px solid {border_color};
                border-radius: 10px;
                padding: 20px;
                margin: 20px 0;
            ">
                <h3 style="color: {border_color}; margin: 0;"> {status}</h3>
                <h1 style="color: {border_color}; margin: 10px 0; font-size: 3rem;">{score:.0f}%</h1>
                <p style="color: #333; margin: 0; font-size: 1.1rem;">Fairness Score</p>
            </div>
        """, unsafe_allow_html=True)
        
        ai_explanation = generate_ai_explanation(fairness_data)
        st.info(f" **AI Analysis:** {ai_explanation}")
        
        if st.session_state.expenses:
            st.markdown("#### Category Breakdown")
            for expense in st.session_state.expenses:
                total = sum(m['amount'] for m in expense['members'])
                members_str = ", ".join([f"{m['name']} (${m['amount']:.2f})" for m in expense['members']])
                st.markdown(f"**{expense['category']}:** ${total:.2f} - {members_str}")
            st.markdown("---")
        
        st.markdown("#### Contribution Details")
        avg = fairness_data['avg_contribution']
        st.write(f"**Average Contribution:** ${avg:.2f}")
        
        for detail in fairness_data['details']:
            diff = detail['difference']
            if diff > 0:
                diff_text = f"+${abs(diff):.2f} above average"
                color = "#28a745"
            elif diff < 0:
                diff_text = f"-${abs(diff):.2f} below average"
                color = "#dc3545"
            else:
                diff_text = "exactly average"
                color = "#6c757d"
            
            st.markdown(f"<p><b>{detail['name']}:</b> ${detail['amount']:.2f} <span style='color: {color};'>({diff_text})</span></p>", unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### Settlement Suggestions")
        
        members_for_settlement = all_members_combined if all_members_combined else st.session_state.members
        settlements = calculate_settlements(members_for_settlement)
        
        if settlements:
            st.write("**To settle this expense fairly, here's who should pay whom:**")
            for idx, settlement in enumerate(settlements, 1):
                st.markdown(f"""
                    <div style="
                        background-color: #e3f2fd;
                        border-left: 4px solid #2196f3;
                        padding: 12px 16px;
                        margin: 8px 0;
                        border-radius: 4px;
                    ">
                        <strong>{idx}.</strong> <strong style="color: #1976d2;">{settlement['from']}</strong> pays <strong style="color: #1976d2;">{settlement['to']}</strong>: <strong style="color: #2e7d32; font-size: 1.1rem;">${settlement['amount']:.2f}</strong>
                    </div>
                """, unsafe_allow_html=True)
            
            total_transactions = len(settlements)
            st.success(f" All debts can be settled with just {total_transactions} transaction{'s' if total_transactions != 1 else ''}!")
        else:
            st.info(" Everyone contributed their fair share! No settlements needed.")
        
        st.markdown("---")
        st.markdown("###  Blockchain Simulation")
        
        with st.spinner("Locking funds in Solana escrow..."):
            time.sleep(1)
            tx_id = generate_transaction_id()
        
        st.success(f" Funds locked in Solana escrow (simulated)")
        st.code(f"Transaction ID: {tx_id}", language=None)
        
        st.markdown("---")
        st.markdown("### Contribution Visualization")
        members_for_viz = all_members_combined if all_members_combined else st.session_state.members
        render_visualization(members_for_viz)
        
        st.markdown("---")
        st.markdown("### Export Data")
        
        col_exp1, col_exp2 = st.columns(2)
        
        members_for_export = all_members_combined if all_members_combined else st.session_state.members
        
        with col_exp1:
            csv_data = generate_csv_export(members_for_export, fairness_data, settlements)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            st.download_button(
                label=" Download CSV",
                data=csv_data,
                file_name=f"fairsplit_summary_{timestamp}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col_exp2:
            pdf_data = generate_pdf_export(members_for_export, fairness_data, settlements)
            st.download_button(
                label=" Download PDF",
                data=pdf_data,
                file_name=f"fairsplit_summary_{timestamp}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        
        st.markdown("---")
        st.markdown("### Save to History")
        
        col_save1, col_save2 = st.columns([2, 1])
        with col_save1:
            group_name = st.text_input("Group Name", placeholder="e.g., Weekend Trip with Friends", key="save_group_name")
        with col_save2:
            group_category = st.selectbox("Category", ["General", "Trip", "Dinner", "Monthly Bills", "Event", "Other"], key="save_category")
        
        group_description = st.text_area("Description (optional)", placeholder="Add notes about this expense...", key="save_description")
        
        if st.button(" Save This Group", type="primary"):
            if group_name.strip():
                try:
                    members_to_save = all_members_combined if all_members_combined else st.session_state.members
                    total = sum(m['amount'] for m in members_to_save)
                    group_id = db.save_group(
                        name=group_name.strip(),
                        description=group_description.strip() if group_description else None,
                        category=group_category,
                        members=members_to_save,
                        fairness_score=fairness_data['score'],
                        total_amount=total
                    )
                    st.success(f"Group '{group_name}' saved successfully! (ID: {group_id})")
                except Exception as e:
                    st.error(f"Failed to save group: {str(e)}")
            else:
                st.error("Please enter a group name.")
    
    elif st.session_state.members and len(st.session_state.members) < 2:
        st.warning("Please add at least 2 members to calculate fairness.")
    
    st.markdown("<div class='footer'>Powered by Meta Llama + Solana Devnet Simulation</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
