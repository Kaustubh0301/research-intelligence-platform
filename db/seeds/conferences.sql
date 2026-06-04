-- Seed data: the 10 target conferences

INSERT INTO conferences (short_name, full_name, field, website) VALUES
    ('NeurIPS', 'Neural Information Processing Systems',            'ML',  'https://neurips.cc'),
    ('ICML',    'International Conference on Machine Learning',     'ML',  'https://icml.cc'),
    ('ICLR',    'International Conference on Learning Representations', 'ML', 'https://iclr.cc'),
    ('CVPR',    'Conference on Computer Vision and Pattern Recognition', 'CV', 'https://cvpr.cc'),
    ('ICCV',    'International Conference on Computer Vision',      'CV',  'https://iccv2025.thecvf.com'),
    ('ECCV',    'European Conference on Computer Vision',           'CV',  'https://eccv.ecva.net'),
    ('ACL',     'Annual Meeting of the Association for Computational Linguistics', 'NLP', 'https://aclweb.org'),
    ('EMNLP',   'Empirical Methods in Natural Language Processing', 'NLP', 'https://2024.emnlp.org'),
    ('AAAI',    'AAAI Conference on Artificial Intelligence',       'AI',  'https://aaai.org'),
    ('IJCAI',   'International Joint Conference on Artificial Intelligence', 'AI', 'https://ijcai.org')
ON CONFLICT (short_name) DO NOTHING;
