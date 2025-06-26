import streamlit as st
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
import pandas as pd
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="SEO Analyzer", page_icon="🔍", layout="wide")
st.title("🔍 Analisador de Sitemap.xml e Robots.txt")

# Sidebar com informações
st.sidebar.header("Sobre")
st.sidebar.info("""
Esta ferramenta analisa arquivos sitemap.xml e robots.txt de sites, fornecendo:
- Estrutura do site
- Bloqueios de rastreamento
- Problemas potenciais de SEO
- Recomendações de otimização
""")

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def fetch_robots_txt(base_url):
    robots_url = urljoin(base_url, '/robots.txt')
    try:
        response = requests.get(robots_url, timeout=10)
        if response.status_code == 200:
            return response.text
        return None
    except:
        return None

def parse_robots_txt(content):
    if not content:
        return None
    
    data = {
        'user_agents': {},
        'sitemaps': [],
        'disallowed': [],
        'allowed': [],
        'crawl_delay': None,
        'comments': []
    }
    
    current_ua = '*'
    
    for line in content.split('\n'):
        line = line.strip()
        
        # Ignorar linhas vazias
        if not line:
            continue
            
        # Comentários
        if line.startswith('#'):
            data['comments'].append(line[1:].strip())
            continue
            
        # User-agent
        if line.lower().startswith('user-agent:'):
            current_ua = line[11:].strip()
            if current_ua not in data['user_agents']:
                data['user_agents'][current_ua] = {'disallow': [], 'allow': []}
            continue
            
        # Disallow
        if line.lower().startswith('disallow:'):
            path = line[9:].strip()
            if path and current_ua in data['user_agents']:
                data['user_agents'][current_ua]['disallow'].append(path)
                data['disallowed'].append(path)
            continue
            
        # Allow
        if line.lower().startswith('allow:'):
            path = line[6:].strip()
            if path and current_ua in data['user_agents']:
                data['user_agents'][current_ua]['allow'].append(path)
                data['allowed'].append(path)
            continue
            
        # Sitemap
        if line.lower().startswith('sitemap:'):
            sitemap_url = line[8:].strip()
            data['sitemaps'].append(sitemap_url)
            continue
            
        # Crawl-delay
        if line.lower().startswith('crawl-delay:'):
            delay = line[12:].strip()
            data['crawl_delay'] = delay
            continue
    
    return data

def fetch_sitemap(sitemap_url):
    try:
        response = requests.get(sitemap_url, timeout=10)
        if response.status_code == 200:
            return response.content
        return None
    except:
        return None

def parse_sitemap(content):
    if not content:
        return None
    
    # Tentar parsear como XML
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        # Pode ser um sitemap index
        try:
            soup = BeautifulSoup(content, 'xml')
            if soup.find('sitemapindex'):
                return {'type': 'index', 'sitemaps': [loc.text for loc in soup.find_all('loc')]}
        except:
            return None
    
    # Verificar se é um sitemap regular
    urls = []
    namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    
    for url in root.findall('ns:url', namespace):
        url_data = {
            'loc': url.find('ns:loc', namespace).text if url.find('ns:loc', namespace) is not None else None,
            'lastmod': url.find('ns:lastmod', namespace).text if url.find('ns:lastmod', namespace) is not None else None,
            'changefreq': url.find('ns:changefreq', namespace).text if url.find('ns:changefreq', namespace) is not None else None,
            'priority': url.find('ns:priority', namespace).text if url.find('ns:priority', namespace) is not None else None
        }
        urls.append(url_data)
    
    if urls:
        return {'type': 'regular', 'urls': urls}
    
    return None

def analyze_seo(robots_data, sitemap_data):
    recommendations = []
    warnings = []
    insights = []
    
    # Análise do robots.txt
    if robots_data:
        # Verificar bloqueios importantes
        important_paths = ['/css/', '/js/', '/img/', '/assets/']
        for path in important_paths:
            if any(path in disallowed for disallowed in robots_data['disallowed']):
                warnings.append(f"⚠️ Bloqueio potencialmente problemático: {path} (pode afetar renderização)")
        
        # Verificar sitemaps
        if not robots_data['sitemaps']:
            recommendations.append("✅ Adicionar diretiva Sitemap no robots.txt")
        else:
            insights.append(f"🔗 Sitemaps encontrados: {len(robots_data['sitemaps'])}")
        
        # Verificar crawl delay
        if robots_data['crawl_delay']:
            insights.append(f"⏱ Crawl delay definido: {robots_data['crawl_delay']}")
    
    # Análise do sitemap
    if sitemap_data:
        if sitemap_data['type'] == 'regular':
            urls = sitemap_data['urls']
            insights.append(f"📊 Total de URLs no sitemap: {len(urls)}")
            
            # Verificar prioridades
            priorities = [float(url['priority']) for url in urls if url['priority']]
            if priorities:
                avg_priority = sum(priorities) / len(priorities)
                insights.append(f"⚖️ Prioridade média: {avg_priority:.2f}")
            
            # Verificar lastmod
            lastmod_dates = [url['lastmod'] for url in urls if url['lastmod']]
            if lastmod_dates:
                try:
                    dates = [datetime.strptime(d, '%Y-%m-%d') for d in lastmod_dates if d]
                    oldest = min(dates).strftime('%Y-%m-%d')
                    newest = max(dates).strftime('%Y-%m-%d')
                    insights.append(f"📅 Datas de modificação: Mais antiga {oldest}, mais recente {newest}")
                except:
                    pass
            
            # Verificar changefreq
            changefreqs = [url['changefreq'] for url in urls if url['changefreq']]
            if changefreqs:
                freq_counts = pd.Series(changefreqs).value_counts()
                insights.append("🔄 Frequência de alterações:")
                for freq, count in freq_counts.items():
                    insights.append(f"   - {freq}: {count} URLs")
        
        elif sitemap_data['type'] == 'index':
            insights.append(f"📂 Sitemap index encontrado com {len(sitemap_data['sitemaps'])} sitemaps")
    
    return recommendations, warnings, insights

# Interface do usuário
url_input = st.text_input("Digite a URL do site (ex: https://example.com):", "")

if url_input:
    if not is_valid_url(url_input):
        st.error("Por favor, insira uma URL válida (incluindo http:// ou https://)")
    else:
        with st.spinner("Analisando o site..."):
            # Processar robots.txt
            st.subheader("🔧 Análise do robots.txt")
            robots_content = fetch_robots_txt(url_input)
            
            if robots_content:
                robots_data = parse_robots_txt(robots_content)
                
                if robots_data:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("### 📝 Conteúdo do robots.txt")
                        st.code(robots_content, language='text')
                    
                    with col2:
                        st.markdown("### 🔍 Insights")
                        
                        # User agents
                        st.markdown("**Agentes de usuário definidos:**")
                        for ua in robots_data['user_agents']:
                            st.write(f"- `{ua}`")
                        
                        # Disallowed
                        if robots_data['disallowed']:
                            st.markdown("**Caminhos bloqueados:**")
                            for path in robots_data['disallowed'][:10]:  # Mostrar apenas os 10 primeiros
                                st.write(f"- `{path}`")
                            if len(robots_data['disallowed']) > 10:
                                st.write(f"... e mais {len(robots_data['disallowed']) - 10} caminhos")
                        
                        # Sitemaps
                        if robots_data['sitemaps']:
                            st.markdown("**Sitemaps encontrados:**")
                            for sitemap in robots_data['sitemaps']:
                                st.write(f"- [{sitemap}]({sitemap})")
                else:
                    st.warning("Não foi possível analisar o robots.txt")
            else:
                st.warning("Robots.txt não encontrado ou não acessível")
            
            # Processar sitemap.xml
            st.subheader("🗺️ Análise do Sitemap.xml")
            
            # Tentar encontrar o sitemap
            sitemap_urls = []
            
            # 1. Verificar se há sitemap no robots.txt
            if robots_data and robots_data['sitemaps']:
                sitemap_urls = robots_data['sitemaps']
            else:
                # 2. Tentar URLs padrão
                common_sitemaps = [
                    '/sitemap.xml',
                    '/sitemap_index.xml',
                    '/sitemap-index.xml',
                    '/sitemap1.xml',
                    '/sitemap_1.xml'
                ]
                for path in common_sitemaps:
                    sitemap_urls.append(urljoin(url_input, path))
            
            sitemap_data = None
            
            for sitemap_url in sitemap_urls:
                sitemap_content = fetch_sitemap(sitemap_url)
                if sitemap_content:
                    sitemap_data = parse_sitemap(sitemap_content)
                    if sitemap_data:
                        st.success(f"Sitemap encontrado em: [{sitemap_url}]({sitemap_url})")
                        break
            
            if sitemap_data:
                if sitemap_data['type'] == 'regular':
                    st.markdown(f"**Tipo:** Sitemap regular com {len(sitemap_data['urls'])} URLs")
                    
                    # Mostrar algumas URLs como exemplo
                    st.markdown("**Algumas URLs do sitemap:**")
                    sample_urls = sitemap_data['urls'][:5]  # Mostrar apenas 5 como exemplo
                    for url in sample_urls:
                        st.write(f"- [{url['loc']}]({url['loc']})")
                    if len(sitemap_data['urls']) > 5:
                        st.write(f"... e mais {len(sitemap_data['urls']) - 5} URLs")
                    
                    # Criar dataframe para análise
                    df = pd.DataFrame(sitemap_data['urls'])
                    
                    # Análise de prioridades
                    if 'priority' in df.columns and not df['priority'].isnull().all():
                        st.markdown("**Distribuição de prioridades:**")
                        st.bar_chart(df['priority'].value_counts())
                    
                    # Análise de changefreq
                    if 'changefreq' in df.columns and not df['changefreq'].isnull().all():
                        st.markdown("**Frequência de alterações:**")
                        st.bar_chart(df['changefreq'].value_counts())
                
                elif sitemap_data['type'] == 'index':
                    st.markdown(f"**Tipo:** Sitemap index com {len(sitemap_data['sitemaps'])} sitemaps")
                    st.markdown("**Sitemaps listados:**")
                    for sitemap in sitemap_data['sitemaps'][:5]:  # Mostrar apenas 5 como exemplo
                        st.write(f"- [{sitemap}]({sitemap})")
                    if len(sitemap_data['sitemaps']) > 5:
                        st.write(f"... e mais {len(sitemap_data['sitemaps']) - 5} sitemaps")
            else:
                st.warning("Não foi possível encontrar ou analisar nenhum sitemap")
            
            # Análise combinada e recomendações
            st.subheader("📊 Análise Combinada e Recomendações")
            
            if robots_data or sitemap_data:
                recommendations, warnings, insights = analyze_seo(robots_data, sitemap_data)
                
                if warnings:
                    st.markdown("### ⚠️ Possíveis Problemas")
                    for warning in warnings:
                        st.warning(warning)
                
                if insights:
                    st.markdown("### 🔍 Insights")
                    for insight in insights:
                        st.info(insight)
                
                if recommendations:
                    st.markdown("### ✅ Recomendações")
                    for rec in recommendations:
                        st.success(rec)
            else:
                st.warning("Dados insuficientes para análise combinada")
else:
    st.info("Digite uma URL acima para começar a análise")

# Rodapé
st.markdown("---")
st.markdown("""
**Como usar:**
1. Insira a URL completa do site (com http:// ou https://)
2. O sistema irá buscar e analisar automaticamente o robots.txt e sitemap.xml
3. Revise os insights e recomendações para otimização de SEO
""")
