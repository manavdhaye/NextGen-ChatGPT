from setuptools import find_packages, setup
from typing import List

HYPEN_E_DOT = '-e .'

def get_requirements(file_path: str) -> List[str]:
    """
    Reads the requirements.txt file and returns a list of dependencies.
    """
    requirements = []
    with open(file_path) as file_obj:
        requirements = file_obj.readlines()
        # Remove newline characters
        requirements = [req.replace("\n", "") for req in requirements]
        
        # Remove the '-e .' trigger if it exists in the requirements file
        if HYPEN_E_DOT in requirements:
            requirements.remove(HYPEN_E_DOT)
            
    return requirements

setup(
    name='nextgen-chatgpt',
    version='1.0.0',
    author='Manav Vijay Dhaye',
    author_email='manavdhaye@gmail.com',
    packages=find_packages(),
    # install_requires=get_requirements('requirements.txt')
)


# from setuptools import find_packages, setup
# from typing import List
# import os

# HYPHEN_E_DOT = '-e .'

# def get_requirements(file_path: str) -> List[str]:
#     """Read requirements.txt and return list of dependencies"""
#     requirements = []
    
#     if not os.path.exists(file_path):
#         print(f"⚠️ Warning: {file_path} not found")
#         return requirements
    
#     try:
#         with open(file_path, encoding='utf-8') as file_obj:
#             requirements = file_obj.readlines()
            
#             # Clean up requirements
#             requirements = [
#                 req.strip() 
#                 for req in requirements 
#                 if req.strip() and not req.startswith('#')
#             ]
            
#             # Remove the '-e .' trigger
#             if HYPHEN_E_DOT in requirements:
#                 requirements.remove(HYPHEN_E_DOT)
        
#         return requirements
    
#     except Exception as e:
#         print(f"❌ Error reading requirements: {e}")
#         return []

# setup(
#     name='nextgen-chatgpt',
#     version='1.0.0',
#     author='Manav Vijay Dhaye',
#     author_email='manavdhaye@gmail.com',
#     description='NextGen ChatGPT - Multi-Agent AI Assistant',
#     long_description=open('README.md', encoding='utf-8').read() if os.path.exists('README.md') else '',
#     long_description_content_type='text/markdown',
#     packages=find_packages(),
#     install_requires=get_requirements('requirements.txt'),  # ✅ UNCOMMENTED!
#     python_requires='>=3.8',
#     classifiers=[
#         'Development Status :: 3 - Alpha',
#         'Intended Audience :: Developers',
#         'Programming Language :: Python :: 3',
#         'Programming Language :: Python :: 3.8',
#         'Programming Language :: Python :: 3.9',
#         'Programming Language :: Python :: 3.10',
#         'Programming Language :: Python :: 3.11',
#     ],
#     keywords='chatbot ai agent langchain',
# )