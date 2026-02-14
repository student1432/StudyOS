# academic_data.py
# System-controlled academic backbone
# Students CANNOT edit this data

ACADEMIC_SYLLABI = {
    # HIGH SCHOOL SYLLABI
    'highschool': {
        'CBSE': {
            '9': {
                'Mathematics': {
                    'chapters': {
                        'Number Systems': {
                            'topics': [
                                {
                                    'name': 'Real Numbers',
                                    'overview': 'Introduction to real numbers, rational and irrational numbers',
                                    'explanations': [
                                        'Real numbers include all the numbers on the number line, including both rational and irrational numbers. They can be positive, negative, or zero.',
                                        'Rational numbers are numbers that can be expressed as a ratio of two integers (p/q where q ≠ 0). They include integers, fractions, and terminating or repeating decimals.',
                                        'Irrational numbers cannot be expressed as simple fractions. Their decimal expansions are non-terminating and non-repeating. Examples include √2, π, and e.'
                                    ],
                                    'key_points': [
                                        'ℝ represents the set of all real numbers',
                                        'Rational numbers (ℚ) are a subset of real numbers',
                                        'Irrational numbers are real numbers that are not rational',
                                        'The decimal expansion of a rational number either terminates or repeats',
                                        'The decimal expansion of an irrational number neither terminates nor repeats'
                                    ],
                                    'images': [
                                        {'url': 'https://www.mathsisfun.com/numbers/images/real-number-system.svg', 'caption': 'Real Number System'},
                                        {'url': 'https://www.cuemath.com/numbers/images/real-numbers-chart.png', 'caption': 'Real Numbers Classification'}
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/watch?v=example1'],
                                        'pdfs': ['https://ncert.nic.in/textbook/pdf/iemaths1.pdf'],
                                        'practice': ['Khan Academy: Real Numbers']
                                    }
                                },
                                {
                                    'name': 'Euclid\'s Division Algorithm',
                                    'overview': 'Understanding Euclid\'s division lemma and algorithm for finding the HCF of two numbers',
                                    'explanations': [
                                        'Euclid\'s Division Lemma states that for any two positive integers a and b, there exist unique integers q and r such that a = bq + r, where 0 ≤ r < b. This forms the basis of the Euclidean algorithm for finding the Highest Common Factor (HCF) of two numbers.',
                                        'The algorithm works by repeatedly applying the division lemma: divide the larger number by the smaller number, then divide the divisor by the remainder, and continue this process until the remainder is zero. The last non-zero remainder is the HCF of the two numbers.',
                                        'This method is efficient and works for any pair of positive integers, making it a fundamental concept in number theory with applications in computer science, particularly in cryptography and algorithm design.'
                                    ],
                                    'key_points': [
                                        'For any two positive integers a and b, a = bq + r where 0 ≤ r < b',
                                        'The algorithm terminates when the remainder becomes zero',
                                        'The last non-zero remainder is the HCF of a and b',
                                        'Works for any pair of positive integers',
                                        'Basis for many number-theoretic algorithms'
                                    ],
                                    'images': [
                                        {'url': 'https://www.math-only-math.com/images/euclids-division-algorithm.png', 'caption': 'Visualization of Euclid\'s Division Algorithm'},
                                        {'url': 'https://www.cuemath.com/algebra/euclids-division-algorithm/images/euclids-division-algorithm-formula.png', 'caption': 'Euclidean Algorithm Steps'}
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/watch?v=AJn843kplDw'],
                                        'pdfs': ['https://ncert.nic.in/ncerts/l/jeep201.pdf'],
                                        'practice': ['Practice problems on Khan Academy', 'NCERT Exercises']
                                    }
                                }
                            ]
                        },
                        'Polynomials': {
                            'topics': [
                                {
                                    'name': 'Polynomials',
                                    'overview': 'Understanding polynomials, degrees, and basic operations',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                },
                                {
                                    'name': 'Linear Equations in Two Variables',
                                    'overview': 'Solving linear equations with two variables',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Linear Equation in Two Variables': {
                            'topics': [
                                {
                                    'name': 'Polynomials',
                                    'overview': 'Understanding polynomials, degrees, and basic operations',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                },
                                {
                                    'name': 'Linear Equations in Two Variables',
                                    'overview': 'Solving linear equations with two variables',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Co-Ordinate Geometry': {
                            'topics': [
                                {
                                    'name': 'Polynomials',
                                    'overview': 'Understanding polynomials, degrees, and basic operations',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                },
                                {
                                    'name': 'Linear Equations in Two Variables',
                                    'overview': 'Solving linear equations with two variables',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Euclidean Geometry': {
                            'topics': [
                                {
                                    'name': 'Polynomials',
                                    'overview': 'Understanding polynomials, degrees, and basic operations',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                },
                                {
                                    'name': 'Linear Equations in Two Variables',
                                    'overview': 'Solving linear equations with two variables',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Lines and Angles': {
                            'topics': [
                                {
                                    'name': 'Polynomials',
                                    'overview': 'Understanding polynomials, degrees, and basic operations',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                },
                                {
                                    'name': 'Linear Equations in Two Variables',
                                    'overview': 'Solving linear equations with two variables',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Triangles': {
                            'topics': [
                                {
                                    'name': 'Polynomials',
                                    'overview': 'Understanding polynomials, degrees, and basic operations',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                },
                                {
                                    'name': 'Linear Equations in Two Variables',
                                    'overview': 'Solving linear equations with two variables',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Quadrilaterals': {
                            'topics': [
                                {
                                    'name': 'Polynomials',
                                    'overview': 'Understanding polynomials, degrees, and basic operations',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                },
                                {
                                    'name': 'Linear Equations in Two Variables',
                                    'overview': 'Solving linear equations with two variables',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Circles': {
                            'topics': [
                                {
                                    'name': 'Polynomials',
                                    'overview': 'Understanding polynomials, degrees, and basic operations',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                },
                                {
                                    'name': 'Linear Equations in Two Variables',
                                    'overview': 'Solving linear equations with two variables',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Heron"s Formula': {
                            'topics': [
                                {
                                    'name': 'Polynomials',
                                    'overview': 'Understanding polynomials, degrees, and basic operations',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                },
                                {
                                    'name': 'Linear Equations in Two Variables',
                                    'overview': 'Solving linear equations with two variables',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Surface Area and Volume': {
                            'topics': [
                                {
                                    'name': 'Polynomials',
                                    'overview': 'Understanding polynomials, degrees, and basic operations',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                },
                                {
                                    'name': 'Linear Equations in Two Variables',
                                    'overview': 'Solving linear equations with two variables',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Statistics': {
                            'topics': [
                                {
                                    'name': 'Polynomials',
                                    'overview': 'Understanding polynomials, degrees, and basic operations',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                },
                                {
                                    'name': 'Linear Equations in Two Variables',
                                    'overview': 'Solving linear equations with two variables',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },
                'Chemistry': {
                    'chapters': {
                        'Matter in Our Surroundings': {
                            'topics': [
                                {
                                    'name': 'States of Matter',
                                    'overview': 'Solid, liquid, and gas - understanding properties',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                },
                                {
                                    'name': 'Change of State',
                                    'overview': 'Temperature and pressure effects on matter',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Is Matter Around Us Pure?': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Atoms and Molecules': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Structure of the Atom': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                    }
                },
                'Physics': {
                    'chapters': {
                        'Motion': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Force and Laws of Motion': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Gravitation': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Work and Energy': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Sound': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                    }
                },
                'Biology': {
                    'chapters': {
                        'Fundamental Unit of Life': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Tissues': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Improvement in Food Resoures': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    ,
                    }
                },
                'History': {
                    'chapters': {
                        'The French Revolution': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Socialism in Europe and the Russian Revolution': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Nazism and the Rise of Hitler': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Pastoralists in the Modern World - Only Periodic Assessment': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    ,
                    }
                },
                'Geography': {
                    'chapters': {
                        'India - Size and Location': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Physical Features of India': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Drainage': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Climate': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Population': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },
                'Political Science': {
                    'chapters': {
                        'What is Democracy? Why Democracy?': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Constitutional Design': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Electoral Politics': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Working of Institution': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Democratic Rights': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },
                'Economics': {
                    'chapters': {
                        'The Story of Village Palampur - Only Periodic Assessment': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'People as Resource': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Poverty as a Challenge': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Food Security in India': {
                            'topics': [
                                {
                                    'name': 'Distance and Displacement',
                                    'overview': 'Understanding scalar and vector quantities',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },
            },
            '10': {
                'Mathematics': {
                    'chapters': {
                        'Real Numbers': {
                            'topics': [
                                {
                                    'name': 'Euclid\'s Division Lemma',
                                    'overview': 'Advanced concepts in division algorithm',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                },
                                {
                                    'name': 'Fundamental Theorem of Arithmetic',
                                    'overview': 'Prime factorization and uniqueness',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Polynomials': {
                            'topics': [
                                {
                                    'name': 'Geometric Meaning of Zeros',
                                    'overview': 'Graphical representation of polynomial zeros',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Pair of Linear Equations in Two Variables': {
                            'topics': [
                                {
                                    'name': 'Geometric Meaning of Zeros',
                                    'overview': 'Graphical representation of polynomial zeros',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Quadratic Equations': {
                            'topics': [
                                {
                                    'name': 'Geometric Meaning of Zeros',
                                    'overview': 'Graphical representation of polynomial zeros',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Arithmetic Progressions': {
                            'topics': [
                                {
                                    'name': 'Geometric Meaning of Zeros',
                                    'overview': 'Graphical representation of polynomial zeros',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Triangles': {
                            'topics': [
                                {
                                    'name': 'Geometric Meaning of Zeros',
                                    'overview': 'Graphical representation of polynomial zeros',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Coordinate Geometry': {
                            'topics': [
                                {
                                    'name': 'Geometric Meaning of Zeros',
                                    'overview': 'Graphical representation of polynomial zeros',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Introduction to Trigonometry': {
                            'topics': [
                                {
                                    'name': 'Geometric Meaning of Zeros',
                                    'overview': 'Graphical representation of polynomial zeros',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Some Applications of Trigonometry': {
                            'topics': [
                                {
                                    'name': 'Geometric Meaning of Zeros',
                                    'overview': 'Graphical representation of polynomial zeros',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Circles': {
                            'topics': [
                                {
                                    'name': 'Geometric Meaning of Zeros',
                                    'overview': 'Graphical representation of polynomial zeros',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Areas Related to Circles': {
                            'topics': [
                                {
                                    'name': 'Geometric Meaning of Zeros',
                                    'overview': 'Graphical representation of polynomial zeros',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Surface Area and Volumes': {
                            'topics': [
                                {
                                    'name': 'Geometric Meaning of Zeros',
                                    'overview': 'Graphical representation of polynomial zeros',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Statistics': {
                            'topics': [
                                {
                                    'name': 'Geometric Meaning of Zeros',
                                    'overview': 'Graphical representation of polynomial zeros',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Probability': {
                            'topics': [
                                {
                                    'name': 'Geometric Meaning of Zeros',
                                    'overview': 'Graphical representation of polynomial zeros',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },
                'Chemistry': {
                    'chapters': {
                        'Chemical Reactions and Equations': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Acids, Bases, and Salts': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Metals and Non Metals': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Carbon and Its Compounds': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },
                'Chemistry': {
                    'chapters': {
                        'Chemical Reactions and Equations': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Acids, Bases, and Salts': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Metals and Non Metals': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Carbon and Its Compounds': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },
                'Physics': {
                    'chapters': {
                        'Light - Reflection and Refraction': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'The Human Eye and the Colourful World': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Electricity': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Magnetic Effects of Electric Current': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },   
                'Biology': {
                    'chapters': {
                        'Life Processes': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Control and Coordination': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'How do Organisms Reproduce?': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Heredity': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Our Environment': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },  
                'Democratic Politics': {
                    'chapters': {
                        'Power Sharing': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Federalism': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Gender, Religion and Caste': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Political Parties': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Outcomes of Democracy': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },  
                'History': {
                    'chapters': {
                        'The Rise of Nationalism in Europe': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Nationalism in India': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'The Making of a Global World': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'The Age of Industrialisation': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Print Culture and the Modern World': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },  
                'Geography': {
                    'chapters': {
                        'Resources and Development': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Forest and Wildlife Resources': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Water Resources': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Agriculture': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Minerals and Energy Resources': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Manufacturing Industries': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Lifelines of National Economy': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },
                'Economics': {
                    'chapters': {
                        'Development': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Sectors of the Indian Economy': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Money and Credit': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Globalisation and The Indian Economy': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Consumer Rights': {
                            'topics': [
                                {
                                    'name': 'Types of Reactions',
                                    'overview': 'Combination, decomposition, displacement reactions',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                }     
            },
            '11': {
                'Physics': {
                    'chapters': {
                        'Physical World': {
                            'topics': [
                                {
                                    'name': 'What is Physics',
                                    'overview': 'Scope and excitement of physics',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        },
                        'Kinematics': {
                            'topics': [
                                {
                                    'name': 'Motion in a Straight Line',
                                    'overview': 'Position, velocity, acceleration',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },
                'Chemistry': {
                    'chapters': {
                        'Some Basic Concepts of Chemistry': {
                            'topics': [
                                {
                                    'name': 'Importance of Chemistry',
                                    'overview': 'Role of chemistry in daily life',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },
                'Mathematics': {
                    'chapters': {
                        'Sets': {
                            'topics': [
                                {
                                    'name': 'Introduction to Sets',
                                    'overview': 'Set notation and operations',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },
                'Biology': {
                    'chapters': {
                        'The Living World': {
                            'topics': [
                                {
                                    'name': 'What is Living?',
                                    'overview': 'Defining characteristics of living organisms including growth, reproduction, and metabolism.',
                                    'explanations': [
                                        'Living organisms are self-replicating, evolving and self-regulating interactive systems capable of responding to external stimuli.',
                                        'The main characteristics include growth, reproduction, ability to sense environment, metabolism, and cellular organization.'
                                    ],
                                    'key_points': [
                                        'Growth: Increase in mass and number',
                                        'Reproduction: Production of progeny',
                                        'Metabolism: Chemical reactions in cells',
                                        'Cellular organization: Basic unit of life'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=biology+the+living+world'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?kebo1=1-22'],
                                        'practice': ['Review Chapter 1 exercises']
                                    }
                                }
                            ]
                        }
                    }
                },
                'Computer Science': {
                    'chapters': {
                        'Computer Systems and Organisation': {
                            'topics': [
                                {
                                    'name': 'Basic Computer Organization',
                                    'overview': 'Introduction to computer system hardware and software components.',
                                    'explanations': [
                                        'A computer system consists of hardware and software components working together to process data.',
                                        'Key components include the CPU (Central Processing Unit), Memory (RAM/ROM), Storage devices, and Input/Output devices.'
                                    ],
                                    'key_points': [
                                        'CPU: Brain of the computer',
                                        'Memory: Temporary and permanent storage',
                                        'Input Devices: Keyboard, Mouse',
                                        'Output Devices: Monitor, Printer'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=basic+computer+organization'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?kecs1=1-13'],
                                        'practice': ['Draw block diagram of computer system']
                                    }
                                }
                            ]
                        }
                    }
                },
                'Economics': {
                    'chapters': {
                        'Introduction to Microeconomics': {
                            'topics': [
                                {
                                    'name': 'Economy',
                                    'overview': 'Central problems of an economy and basic concepts.',
                                    'explanations': [
                                        'Economics is the study of how societies use scarce resources to produce valuable commodities and distribute them among different people.',
                                        'Microeconomics focuses on the behavior of individual agents and markets.'
                                    ],
                                    'key_points': [
                                        'Scarcity: Limited resources vs unlimited wants',
                                        'Choice: Allocation of resources',
                                        'Opportunity Cost: Value of next best alternative'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=introduction+to+microeconomics'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?keec1=1-6'],
                                        'practice': ['Define scarcity and choice']
                                    }
                                }
                            ]
                        }
                    }
                },
                'Accountancy': {
                    'chapters': {
                        'Introduction to Accounting': {
                            'topics': [
                                {
                                    'name': 'Meaning and Scope',
                                    'overview': 'Objectives, advantages and limitations of accounting.',
                                    'explanations': [
                                        'Accounting is the art of recording, classifying, and summarizing in a significant manner and in terms of money, transactions and events which are, in part at least, of financial character, and interpreting the results thereof.'
                                    ],
                                    'key_points': [
                                        'Recording financial transactions',
                                        'Classifying into ledgers',
                                        'Summarizing into trial balance',
                                        'Interpreting financial statements'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=introduction+to+accounting+class+11'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?keac1=1-13'],
                                        'practice': ['List 3 objectives of accounting']
                                    }
                                }
                            ]
                        }
                    }
                },
                'Business Studies': {
                    'chapters': {
                        'Nature and Purpose of Business': {
                            'topics': [
                                {
                                    'name': 'Concept of Business',
                                    'overview': 'Human activities and classification of business activities.',
                                    'explanations': [
                                        'Business refers to an occupation in which people regularly engage in activities related to purchase, production and/or sale of goods and services with a view to earning profits.'
                                    ],
                                    'key_points': [
                                        'Economic Activity: Done for earning money',
                                        'Production/Procurement of Goods',
                                        'Sale/Exchange of Goods',
                                        'Profit Earning Motive'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=nature+and+purpose+of+business+class+11'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?kebs1=1-11'],
                                        'practice': ['Distinguish between business, profession and employment']
                                    }
                                }
                            ]
                        }
                    }
                },
                'History': {
                    'chapters': {
                        'From the Beginning of Time': {
                            'topics': [
                                {
                                    'name': 'Human Evolution',
                                    'overview': 'Early humans, their development, and use of tools.',
                                    'explanations': [
                                        'This chapter traces the beginning of human existence, focusing on the evolution of early humans from primates, their migration, and the development of stone tools and language.'
                                    ],
                                    'key_points': [
                                        'Primates to Hominids evolution',
                                        'Homo habilis, Homo erectus, Homo sapiens',
                                        'Stone Age tools',
                                        'Cave paintings and communication'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=history+class+11+chapter+1'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?kehs1=1-4'],
                                        'practice': ['Map the migration of early humans']
                                    }
                                }
                            ]
                        }
                    }
                },
                'Geography': {
                    'chapters': {
                        'Geography as a Discipline': {
                            'topics': [
                                {
                                    'name': 'Geography as an Integrating Discipline',
                                    'overview': 'Scope of geography and its relation to other sciences.',
                                    'explanations': [
                                        'Geography is concerned with the description and explanation of the areal differentiation of the earth\'s surface. It integrates data from natural and social sciences.'
                                    ],
                                    'key_points': [
                                        'Physical Geography',
                                        'Human Geography',
                                        'Biogeography',
                                        'Geographical Information System (GIS)'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=geography+class+11+chapter+1'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?kegy1=1-6'],
                                        'practice': ['Explain the scope of physical geography']
                                    }
                                }
                            ]
                        }
                    }
                },
                'Political Science': {
                    'chapters': {
                        'Constitution: Why and How?': {
                            'topics': [
                                {
                                    'name': 'Why do we need a Constitution?',
                                    'overview': 'Functions of a constitution and how the Indian Constitution was made.',
                                    'explanations': [
                                        'A constitution is a set of fundamental principles or established precedents according to which a state or other organization is acknowledged to be governed.'
                                    ],
                                    'key_points': [
                                        'Coordination and assurance',
                                        'Specification of decision-making powers',
                                        'Limitations on the powers of government',
                                        'Aspirations and goals of a society'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=political+science+class+11+chapter+1'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?keps1=1-10'],
                                        'practice': ['What is the function of the preamble?']
                                    }
                                }
                            ]
                        }
                    }
                },
                'English': {
                    'chapters': {
                        'The Portrait of a Lady': {
                            'topics': [
                                {
                                    'name': 'The Portrait of a Lady',
                                    'overview': 'Story analysis, character sketch, and major themes.',
                                    'explanations': [
                                        'The story describes the author\'s relationship with his grandmother, capturing her daily routine, her spirituality, and her fading presence as he grows up.'
                                    ],
                                    'key_points': [
                                        'Relationship between author and grandmother',
                                        'Village life vs City life',
                                        'Significance of sparrows',
                                        'Acceptance of death'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=the+portrait+of+a+lady+class+11'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?kehb1=1-8'],
                                        'practice': ['Describe the changing relationship between the author and his grandmother']
                                    }
                                }
                            ]
                        }
                    }
                }
            },
            '12': {
                'Physics': {
                    'chapters': {
                        'Electric Charges and Fields': {
                            'topics': [
                                {
                                    'name': 'Electric Charge',
                                    'overview': 'Properties of electric charge',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },
                'Chemistry': {
                    'chapters': {
                        'Solid State': {
                            'topics': [
                                {
                                    'name': 'Classification of Solids',
                                    'overview': 'Crystalline and amorphous solids',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },
                'Mathematics': {
                    'chapters': {
                        'Relations and Functions': {
                            'topics': [
                                {
                                    'name': 'Types of Relations',
                                    'overview': 'Reflexive, symmetric, transitive relations',
                                    'resources': {
                                        'videos': [],
                                        'pdfs': [],
                                        'practice': []
                                    }
                                }
                            ]
                        }
                    }
                },
                'Biology': {
                    'chapters': {
                        'Reproduction in Organisms': {
                            'topics': [
                                {
                                    'name': 'Asexual Reproduction',
                                    'overview': 'Modes of asexual reproduction in various organisms.',
                                    'explanations': [
                                        'Asexual reproduction involves the production of offspring from a single parent without the fusion of gametes.',
                                        'Common modes include binary fission, budding, sporulation, and vegetative propagation.'
                                    ],
                                    'key_points': [
                                        'Single parent involved',
                                        'Offspring are clones',
                                        'Rapid multiplication',
                                        'Common in lower organisms'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=reproduction+in+organisms+class+12'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?lebo1=1-18'],
                                        'practice': ['Define clone']
                                    }
                                }
                            ]
                        }
                    }
                },
                'Computer Science': {
                    'chapters': {
                        'Python Revision Tour': {
                            'topics': [
                                {
                                    'name': 'Review of Python Basics',
                                    'overview': 'Revision of Python concepts covered in Class 11.',
                                    'explanations': [
                                        'Reviewing variables, data types, operators, expressions, and control flow statements (if-else, loops).',
                                        'Understanding functions, strings, lists, tuples and dictionaries.'
                                    ],
                                    'key_points': [
                                        'Mutable vs Immutable types',
                                        'String manipulation',
                                        'List slicing and methods',
                                        'Dictionary keys and values'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=python+revision+tour+class+12'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?lecs1=1-28'],
                                        'practice': ['Write a program to check palindrome']
                                    }
                                }
                            ]
                        }
                    }
                },
                'Economics': {
                    'chapters': {
                        'Introduction to Macroeconomics': {
                            'topics': [
                                {
                                    'name': 'Introduction',
                                    'overview': 'Basic concepts of macroeconomics and its scope.',
                                    'explanations': [
                                        'Macroeconomics deals with the aggregate economy, studying issues like inflation, unemployment, and economic growth.',
                                        'It emerged as a separate branch of economics after the Great Depression.'
                                    ],
                                    'key_points': [
                                        'Study of aggregates',
                                        'General equilibrium',
                                        'John Maynard Keynes',
                                        'Capitalist economy features'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=introduction+to+macroeconomics+class+12'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?leec1=1-8'],
                                        'practice': ['Difference between micro and macro economics']
                                    }
                                }
                            ]
                        }
                    }
                },
                'Accountancy': {
                    'chapters': {
                        'Accounting for Not-for-Profit Organisations': {
                            'topics': [
                                {
                                    'name': 'Meaning and Features',
                                    'overview': 'Characteristics and accounting treatment for NPO.',
                                    'explanations': [
                                        'Not-for-Profit Organisations (NPO) are set up for the welfare of society and not for earning profits.',
                                        'Their main source of income is subscriptions, donations, and grants.'
                                    ],
                                    'key_points': [
                                        'Receipts and Payments Account',
                                        'Income and Expenditure Account',
                                        'Balance Sheet',
                                        'Fund-based accounting'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=accounting+for+npo+class+12'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?leac1=1-60'],
                                        'practice': ['Prepare Income and Expenditure Account']
                                    }
                                }
                            ]
                        }
                    }
                },
                'Business Studies': {
                    'chapters': {
                        'Nature and Significance of Management': {
                            'topics': [
                                {
                                    'name': 'Management - Concept, Objectives, and Importance',
                                    'overview': 'Definition, features, and importance of management.',
                                    'explanations': [
                                        'Management is the process of designing and maintaining an environment in which individuals, working together in groups, efficiently accomplish selected aims.',
                                        'It is a process of getting things done with the aim of achieving goals effectively and efficiently.'
                                    ],
                                    'key_points': [
                                        'Goal-oriented process',
                                        'Pervasive activity',
                                        'Continuous process',
                                        'Group activity'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=nature+and+significance+of+management+class+12'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?lebs1=1-28'],
                                        'practice': ['Explain management as a profession']
                                    }
                                }
                            ]
                        }
                    }
                },
                'History': {
                    'chapters': {
                        'Bricks, Beads and Bones': {
                            'topics': [
                                {
                                    'name': 'The Harappan Civilisation',
                                    'overview': 'Harappan civilization, its urban centers, and culture.',
                                    'explanations': [
                                        'The Harappan Civilisation (Indus Valley Civilisation) was a Bronze Age civilisation in the northwestern regions of South Asia.',
                                        'It is known for its urban planning, baked brick houses, elaborate drainage systems, water supply systems, and clusters of large non-residential buildings.'
                                    ],
                                    'key_points': [
                                        'Mohenjodaro and Harappa',
                                        'Great Bath',
                                        'Seals and weights',
                                        'Craft production'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=bricks+beads+and+bones+class+12'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?lehs1=1-28'],
                                        'practice': ['Discuss the urban planning of Harappan cities']
                                    }
                                }
                            ]
                        }
                    }
                },
                'Geography': {
                    'chapters': {
                        'Human Geography': {
                            'topics': [
                                {
                                    'name': 'Nature and Scope',
                                    'overview': 'Definition, nature and scope of human geography.',
                                    'explanations': [
                                        'Human geography studies the inter-relationship between the physical environment and socio-cultural environment created by human beings through mutual interaction with each other.'
                                    ],
                                    'key_points': [
                                        'Environmental Determinism',
                                        'Possibilism',
                                        'Neodeterminism (Stop and Go Determinism)',
                                        'Fields of Human Geography'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=human+geography+nature+and+scope'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?legy1=1-10'],
                                        'practice': ['Differentiate between determinism and possibilism']
                                    }
                                }
                            ]
                        }
                    }
                },
                'Political Science': {
                    'chapters': {
                        'The Cold War Era': {
                            'topics': [
                                {
                                    'name': 'Cold War Era',
                                    'overview': 'Emergence of two power blocs and the Cold War.',
                                    'explanations': [
                                        'The Cold War referred to the competition, the tensions and a series of confrontations between the United States and Soviet Union, backed by their respective allies.',
                                        'It never escalated into a hot war directly between the two powers.'
                                    ],
                                    'key_points': [
                                        'Cuban Missile Crisis',
                                        'NATO vs Warsaw Pact',
                                        'Logic of deterrence',
                                        'Non-Aligned Movement (NAM)'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=cold+war+era+class+12'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?leps1=1-16'],
                                        'practice': ['What was the Cuban Missile Crisis?']
                                    }
                                }
                            ]
                        }
                    }
                },
                'English': {
                    'chapters': {
                        'The Last Lesson': {
                            'topics': [
                                {
                                    'name': 'The Last Lesson',
                                    'overview': 'Themes of language, identity and patriotism.',
                                    'explanations': [
                                        'The story is set in the days of the Franco-Prussian War (1870-1871). It deals with the theme of language imposition and the pain of losing one\'s mother tongue.',
                                        'M. Hamel teaches his last French lesson with great emotion.'
                                    ],
                                    'key_points': [
                                        'Impact of war on daily life',
                                        'Importance of mother tongue',
                                        'Regret of procrastination in learning',
                                        'Last day of M. Hamel'
                                    ],
                                    'resources': {
                                        'videos': ['https://www.youtube.com/results?search_query=the+last+lesson+class+12'],
                                        'pdfs': ['https://ncert.nic.in/textbook.php?lefl1=1-9'],
                                        'practice': ['Why did M. Hamel blame himself and others for the neglect of learning French?']
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
    },
    
    # COMPETITIVE EXAM SYLLABI
    'exams': {
        'JEE': {
            'Physics': {
                'chapters': {
                    'Mechanics': {
                        'topics': [
                            {
                                'name': 'Newton\'s Laws of Motion',
                                'overview': 'Three laws and their applications',
                                'resources': {
                                    'videos': ['https://www.youtube.com/watch?v=jee-example'],
                                    'pdfs': [],
                                    'practice': ['JEE Previous Year Questions']
                                }
                            },
                            {
                                'name': 'Work, Energy and Power',
                                'overview': 'Concepts and problem-solving',
                                'resources': {
                                    'videos': [],
                                    'pdfs': [],
                                    'practice': []
                                }
                            }
                        ]
                    },
                    'Electromagnetism': {
                        'topics': [
                            {
                                'name': 'Electrostatics',
                                'overview': 'Coulomb\'s law, electric field',
                                'resources': {
                                    'videos': [],
                                    'pdfs': [],
                                    'practice': []
                                }
                            }
                        ]
                    }
                }
            },
            'Chemistry': {
                'chapters': {
                    'Physical Chemistry': {
                        'topics': [
                            {
                                'name': 'Atomic Structure',
                                'overview': 'Quantum numbers, electron configuration',
                                'resources': {
                                    'videos': [],
                                    'pdfs': [],
                                    'practice': []
                                }
                            }
                        ]
                    },
                    'Organic Chemistry': {
                        'topics': [
                            {
                                'name': 'Hydrocarbons',
                                'overview': 'Alkanes, alkenes, alkynes',
                                'resources': {
                                    'videos': [],
                                    'pdfs': [],
                                    'practice': []
                                }
                            }
                        ]
                    }
                }
            },
            'Mathematics': {
                'chapters': {
                    'Calculus': {
                        'topics': [
                            {
                                'name': 'Limits and Continuity',
                                'overview': 'Fundamental concepts of calculus',
                                'resources': {
                                    'videos': [],
                                    'pdfs': [],
                                    'practice': []
                                }
                            },
                            {
                                'name': 'Differentiation',
                                'overview': 'Derivatives and applications',
                                'resources': {
                                    'videos': [],
                                    'pdfs': [],
                                    'practice': []
                                }
                            }
                        ]
                    },
                    'Algebra': {
                        'topics': [
                            {
                                'name': 'Complex Numbers',
                                'overview': 'Operations on complex numbers',
                                'resources': {
                                    'videos': [],
                                    'pdfs': [],
                                    'practice': []
                                }
                            }
                        ]
                    }
                }
            }
        },
        'NEET': {
            'Physics': {
                'chapters': {
                    'Mechanics': {
                        'topics': [
                            {
                                'name': 'Units and Measurements',
                                'overview': 'SI units, dimensional analysis',
                                'resources': {
                                    'videos': [],
                                    'pdfs': [],
                                    'practice': []
                                }
                            }
                        ]
                    }
                }
            },
            'Chemistry': {
                'chapters': {
                    'Organic Chemistry': {
                        'topics': [
                            {
                                'name': 'Biomolecules',
                                'overview': 'Carbohydrates, proteins, nucleic acids',
                                'resources': {
                                    'videos': [],
                                    'pdfs': [],
                                    'practice': []
                                }
                            }
                        ]
                    }
                }
            },
            'Biology': {
                'chapters': {
                    'Cell Biology': {
                        'topics': [
                            {
                                'name': 'Cell Structure',
                                'overview': 'Prokaryotic and eukaryotic cells',
                                'resources': {
                                    'videos': [],
                                    'pdfs': [],
                                    'practice': []
                                }
                            }
                        ]
                    },
                    'Genetics': {
                        'topics': [
                            {
                                'name': 'Mendelian Genetics',
                                'overview': 'Laws of inheritance',
                                'resources': {
                                    'videos': [],
                                    'pdfs': [],
                                    'practice': []
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
}

def get_syllabus(purpose, board_or_exam, grade=None, subjects=None):
    """
    Get the syllabus dictionary based on purpose, board/exam, and grade.
    Optional: subjects list for after_tenth purpose.
    """
    if purpose == 'highschool' or purpose == 'after_tenth':
        # board_or_exam is the board (e.g., 'CBSE'), grade is '9', '10', '11', '12'
        grade_str = str(grade) if grade else None
        
        # Get board data, fallback to CBSE if board not found (e.g. ICSE, State Board)
        highschool_data = ACADEMIC_SYLLABI.get('highschool', {})
        board_data = highschool_data.get(board_or_exam)
        if not board_data:
             # Fallback to CBSE if specific board data is missing
             board_data = highschool_data.get('CBSE', {})
             
        grade_syllabus = board_data.get(grade_str, {})
        
        if purpose == 'after_tenth' and subjects and isinstance(subjects, list):
            # Return only requested subjects, but ensure we return something if key exists
            return {s: grade_syllabus[s] for s in subjects if s in grade_syllabus}
        return grade_syllabus
    
    elif purpose == 'exam' or purpose == 'exams':
        # board_or_exam is the exam type (e.g., 'JEE', 'NEET')
        return ACADEMIC_SYLLABI.get('exams', {}).get(board_or_exam, {})
    
    return {}

def get_available_subjects(purpose, board_or_exam, grade=None):
    """Get list of available subjects for a given academic path"""
    syllabus = get_syllabus(purpose, board_or_exam, grade)
    return list(syllabus.keys()) if syllabus else []
