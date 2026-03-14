from __future__ import annotations

TOP30_SCHOOLS = [
    "Princeton University",
    "Massachusetts Institute of Technology",
    "Harvard University",
    "Stanford University",
    "Yale University",
    "California Institute of Technology",
    "Duke University",
    "Johns Hopkins University",
    "Northwestern University",
    "University of Pennsylvania",
    "Cornell University",
    "University of Chicago",
    "Brown University",
    "Columbia University",
    "Dartmouth College",
    "University of California, Los Angeles",
    "University of California, Berkeley",
    "Rice University",
    "Vanderbilt University",
    "University of Notre Dame",
    "Carnegie Mellon University",
    "University of Michigan",
    "Washington University in St. Louis",
    "Emory University",
    "Georgetown University",
    "University of Virginia",
    "University of Southern California",
    "University of North Carolina at Chapel Hill",
    "New York University",
    "Tufts University",
]

HOT_MAJORS = ["CS", "EE", "Data Science", "Economics"]

SCHOOL_SELECTIVITY_SCORE = {
    "Princeton University": 0.93,
    "Massachusetts Institute of Technology": 0.95,
    "Harvard University": 0.97,
    "Stanford University": 0.97,
    "Yale University": 0.93,
    "California Institute of Technology": 0.95,
    "Duke University": 0.88,
    "Johns Hopkins University": 0.87,
    "Northwestern University": 0.86,
    "University of Pennsylvania": 0.9,
    "Cornell University": 0.82,
    "University of Chicago": 0.9,
    "Brown University": 0.88,
    "Columbia University": 0.91,
    "Dartmouth College": 0.86,
    "University of California, Los Angeles": 0.75,
    "University of California, Berkeley": 0.8,
    "Rice University": 0.82,
    "Vanderbilt University": 0.8,
    "University of Notre Dame": 0.75,
    "Carnegie Mellon University": 0.83,
    "University of Michigan": 0.7,
    "Washington University in St. Louis": 0.75,
    "Emory University": 0.72,
    "Georgetown University": 0.71,
    "University of Virginia": 0.68,
    "University of Southern California": 0.65,
    "University of North Carolina at Chapel Hill": 0.64,
    "New York University": 0.66,
    "Tufts University": 0.67,
}

MAJOR_DIFFICULTY_SCORE = {
    "CS": 0.95,
    "EE": 0.86,
    "Data Science": 0.88,
    "Economics": 0.72,
}

IELTS_TO_TOEFL = {
    9.0: 118,
    8.5: 115,
    8.0: 110,
    7.5: 102,
    7.0: 96,
    6.5: 85,
    6.0: 74,
}

CURRICULUM_RIGOR_BASE = {
    "AP": 0.82,
    "IB": 0.86,
    "A-Level": 0.8,
    "Other": 0.72,
}
