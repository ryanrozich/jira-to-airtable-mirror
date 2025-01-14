from setuptools import setup, find_packages

setup(
    name='jira-airtable-sync',
    version='0.1.0',
    description='Synchronize Jira issues to Airtable',
    author='Your Name',
    packages=find_packages(),
    install_requires=[
        'jira==3.5.1',
        'airtable-python-wrapper==0.1.3',
        'python-dotenv==1.0.0',
        'click==8.1.7',
        'apscheduler==4.0.0',
        'requests==2.31.0'
    ],
    entry_points={
        'console_scripts': [
            'jira-airtable-sync=sync:main',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)
