import os
from jinja2 import Environment, FileSystemLoader

def render():
    """Renders the index.html.j2 template to index.html"""
    env = Environment(
        loader=FileSystemLoader('templates'),
        autoescape=True
    )
    template = env.get_template('index.html.j2')

    context = {
        'google_analytics_id': os.getenv('GOOGLE_ANALYTICS_ID', ''),
        'maptiler_api_key': os.getenv('MAPTILER_API_KEY', ''),
        'version': os.getenv('VERSION', '1')
    }

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(template.render(context))

if __name__ == '__main__':
    render()
