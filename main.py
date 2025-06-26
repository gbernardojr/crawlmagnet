import streamlit as st
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
import pandas as pd
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="SEO Analyzer Pro", page_icon="🔍", layout="wide")
st.title("🔍 Analisador Avançado de Sitemap.xml e Robots.txt")

# Sidebar com informações
st.sidebar.header("Sobre")
st.sidebar.info("""
Esta ferramenta analisa arquivos sitemap.xml e robots.txt de sites, incluindo:
- Detecção automática de sitemaps indexados
- Análise hierárquica de múltiplos sitemaps
- Diagnóstico completo de bloqueios e estrutura
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
        
        if not line:
            continue
            
        if line.startswith('#'):
            data['comments'].append(line[1:].strip())
            continue
            
        if line.lower().startswith('user-agent:'):
            current_ua = line[11:].strip()
            if current_ua not in data['user_agents']:
                data['user_agents'][current_ua] = {'disallow': [], 'allow': []}
            continue
            
        if line.lower().startswith('disallow:'):
            path = line[9:].strip()
            if path and current_ua in data['user_agents']:
                data['user_agents'][current_ua]['disallow'].append(path)
                data['disallowed'].append(path)
            continue
            
        if line.lower().startswith('allow:'):
            path = line[6:].strip()
            if path and current_ua in data['user_agents']:
                data['user_agents'][current_ua]['allow'].append(path)
                data['allowed'].append(path)
            continue
            
        if line.lower().startswith('sitemap:'):
            sitemap_url = line[8:].strip()
            data['sitemaps'].append(sitemap_url)
            continue
            
        if line.lower().startswith('crawl-delay:'):
            delay = line[12:].strip()
            data['crawl_delay'] = delay
            continue
    
    return data

def fetch_sitemap(sitemap_url):
    try:
        response = requests.get(sitemap_url, timeout=15)
        if response.status_code == 200:
            return response.content
        return None
    except Exception as e:
        st.warning(f"Erro ao acessar {sitemap_url}: {str(e)}")
        return None

def parse_sitemap(content, original_url=None):
    if not content:
        return None
    
    # Tentar parsear como XML
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        try:
            soup = BeautifulSoup(content, 'xml')
            if soup.find('sitemapindex'):
                sitemaps = [loc.text for loc in soup.find_all('loc')]
                return {
                    'type': 'index',
                    'sitemaps': sitemaps,
                    'source': original_url or 'Direct'
                }
            elif soup.find('urlset'):
                urls = []
                for url in soup.find_all('url'):
                    url_data = {
                        'loc': url.find('loc').text if url.find('loc') else None,
                        'lastmod': url.find('lastmod').text if url.find('lastmod') else None,
                        'changefreq': url.find('changefreq').text if url.find('changefreq') else None,
                        'priority': url.find('priority').text if url.find('priority') else None
                    }
                    urls.append(url_data)
                return {
                    'type': 'regular',
                    'urls': urls,
                    'source': original_url or 'Direct'
                }
        except Exception as e:
            st.warning(f"Erro ao analisar sitemap: {str(e)}")
            return None
    
    # Parsear como sitemap regular
    try:
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = []
        
        for url in root.findall('ns:url', namespace):
            url_data = {
                'loc': url.find('ns:loc', namespace).text if url.find('ns:loc', namespace) is not None else None,
                'lastmod': url.find('ns:lastmod', namespace).text if url.find('ns:lastmod', namespace) is not None else None,
                'changefreq': url.find('ns:changefreq', namespace).text if url.find('ns:changefreq', namespace) is not None else None,
                'priority': url.find('ns:priority', namespace).text if url.find('ns:priority', namespace) is not None else None
            }
            urls.append(url_data)
        
        if urls:
            return {
                'type': 'regular',
                'urls': urls,
                'source': original_url or 'Direct'
            }
    except:
        pass
    
    return None

def get_all_sitemap_urls(sitemap_data):
    all_urls = []
    
    if sitemap_data['type'] == 'regular':
        return sitemap_data['urls']
    elif sitemap_data['type'] == 'index':
        for sitemap_url in sitemap_data['sitemaps']:
            content = fetch_sitemap(sitemap_url)
            if content:
                parsed = parse_sitemap(content, sitemap_url)
                if parsed and parsed['type'] == 'regular':
                    all_urls.extend(parsed['urls'])
    
    return all_urls

def analyze_seo(robots_data, sitemap_data):
    recommendations = []
    warnings = []
    insights = []
    
    if robots_data:
        important_paths = ['/css/', '/js/', '/img/', '/assets/']
        for path in important_paths:
            if any(path in disallowed for disallowed in robots_data['disallowed']):
                warnings.append(f"⚠️ Bloqueio potencialmente problemático: {path} (pode afetar renderização)")
        
        if not robots_data['sitemaps']:
            recommendations.append("✅ Adicionar diretiva Sitemap no robots.txt")
        else:
            insights.append(f"🔗 Sitemaps encontrados: {len(robots_data['sitemaps'])}")
        
        if robots_data['crawl_delay']:
            insights.append(f"⏱ Crawl delay definido: {robots_data['crawl_delay']}")
    
    if sitemap_data:
        if sitemap_data['type'] == 'regular':
            urls = sitemap_data['urls']
            insights.append(f"📊 URLs no sitemap principal: {len(urls)}")
            
            priorities = [float(url['priority']) for url in urls if url['priority']]
            if priorities:
                avg_priority = sum(priorities) / len(priorities)
                insights.append(f"⚖️ Prioridade média: {avg_priority:.2f}")
            
            lastmod_dates = [url['lastmod'] for url in urls if url['lastmod']]
            if lastmod_dates:
                try:
                    dates = [datetime.strptime(d, '%Y-%m-%d') for d in lastmod_dates if d]
                    oldest = min(dates).strftime('%Y-%m-%d')
                    newest = max(dates).strftime('%Y-%m-%d')
                    insights.append(f"📅 Datas de modificação: Mais antiga {oldest}, mais recente {newest}")
                except:
                    pass
            
            changefreqs = [url['changefreq'] for url in urls if url['changefreq']]
            if changefreqs:
                freq_counts = pd.Series(changefreqs).value_counts()
                insights.append("🔄 Frequência de alterações:")
                for freq, count in freq_counts.items():
                    insights.append(f"   - {freq}: {count} URLs")
        
        elif sitemap_data['type'] == 'index':
            insights.append(f"📂 Sitemap index encontrado com {len(sitemap_data['sitemaps'])} sitemaps vinculados")
            
            # Analisar todos os sitemaps vinculados
            all_urls = get_all_sitemap_urls(sitemap_data)
            if all_urls:
                insights.append(f"🌐 Total de URLs em todos os sitemaps: {len(all_urls)}")
                
                # Adicionar análise agregada
                priorities = [float(url['priority']) for url in all_urls if url.get('priority')]
                if priorities:
                    avg_priority = sum(priorities) / len(priorities)
                    insights.append(f"⚖️ Prioridade média combinada: {avg_priority:.2f}")
    
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
                        
                        st.markdown("**Agentes de usuário definidos:**")
                        for ua in robots_data['user_agents']:
                            st.write(f"- `{ua}`")
                        
                        if robots_data['disallowed']:
                            st.markdown("**Caminhos bloqueados:**")
                            for path in robots_data['disallowed'][:10]:
                                st.write(f"- `{path}`")
                            if len(robots_data['disallowed']) > 10:
                                st.write(f"... e mais {len(robots_data['disallowed']) - 10} caminhos")
                        
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
            
            if robots_data and robots_data['sitemaps']:
                sitemap_urls = robots_data['sitemaps']
            else:
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
                    sitemap_data = parse_sitemap(sitemap_content, sitemap_url)
                    if sitemap_data:
                        st.success(f"Sitemap encontrado em: [{sitemap_url}]({sitemap_url})")
                        break
            
            if sitemap_data:
                if sitemap_data['type'] == 'regular':
                    st.markdown(f"**Tipo:** Sitemap regular com {len(sitemap_data['urls'])} URLs")
                    
                    st.markdown("**Algumas URLs do sitemap:**")
                    sample_urls = sitemap_data['urls'][:5]
                    for url in sample_urls:
                        st.write(f"- [{url['loc']}]({url['loc']})")
                    if len(sitemap_data['urls']) > 5:
                        st.write(f"... e mais {len(sitemap_data['urls']) - 5} URLs")
                    
                    df = pd.DataFrame(sitemap_data['urls'])
                    
                    if 'priority' in df.columns and not df['priority'].isnull().all():
                        st.markdown("**Distribuição de prioridades:**")
                        st.bar_chart(df['priority'].value_counts())
                    
                    if 'changefreq' in df.columns and not df['changefreq'].isnull().all():
                        st.markdown("**Frequência de alterações:**")
                        st.bar_chart(df['changefreq'].value_counts())
                
                elif sitemap_data['type'] == 'index':
                    st.markdown(f"**Tipo:** Sitemap index com {len(sitemap_data['sitemaps'])} sitemaps vinculados")
                    st.markdown("**Sitemaps listados:**")
                    for sitemap in sitemap_data['sitemaps'][:5]:
                        st.write(f"- [{sitemap}]({sitemap})")
                    if len(sitemap_data['sitemaps']) > 5:
                        st.write(f"... e mais {len(sitemap_data['sitemaps']) - 5} sitemaps")
                    
                    # Mostrar análise combinada dos sitemaps vinculados
                    with st.expander("🔍 Ver análise detalhada de todos os sitemaps"):
                        all_urls = get_all_sitemap_urls(sitemap_data)
                        if all_urls:
                            st.markdown(f"**Total de URLs encontradas em todos os sitemaps:** {len(all_urls)}")
                            
                            # Criar dataframe combinado
                            combined_df = pd.DataFrame(all_urls)
                            
                            if 'priority' in combined_df.columns and not combined_df['priority'].isnull().all():
                                st.markdown("**Distribuição combinada de prioridades:**")
                                st.bar_chart(combined_df['priority'].value_counts())
                            
                            if 'lastmod' in combined_df.columns and not combined_df['lastmod'].isnull().all():
                                try:
                                    combined_df['lastmod_date'] = pd.to_datetime(combined_df['lastmod'])
                                    st.markdown("**Distribuição temporal das atualizações:**")
                                    st.line_chart(combined_df['lastmod_date'].value_counts().sort_index())
                                except:
                                    pass
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
2. O sistema buscará robots.txt e sitemap.xml (incluindo sitemaps indexados)
3. Revise os insights e recomendações para otimização
""")
