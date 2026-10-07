"""SKETCH, not tested: how the JSON feature input would be replaced by reading the part inside Siemens NX.

Runs only inside NX (Tools > Journal > Play, or as an NX Open application) and needs an NX licence.
The rule engine, validation and JSON export of this repository stay unchanged; only the feature source changes.
"""
import NXOpen  # available only inside the NX Python environment


def read_faces():
    session = NXOpen.Session.GetSession()
    work_part = session.Parts.Work
    planar, cylindrical = [], []
    for body in work_part.Bodies:
        for face in body.GetFaces():
            if face.SolidFaceType == NXOpen.Face.FaceType.Planar:
                planar.append(face)
            elif face.SolidFaceType == NXOpen.Face.FaceType.Cylindrical:
                cylindrical.append(face)
    return planar, cylindrical

# Next steps (to be implemented in NX):
# 1. Measure each face (area of planar faces, radius and axis of cylindrical faces) and classify holes
#    by diameter and by the attributes/feature type (e.g. NX Hole features carry fastener size).
# 2. Map them onto pmi_assistant.model.Feature and call rules.generate() + validate.validate().
# 3. Write the suggested datums, feature control frames and notes back as PMI objects
#    (work_part.PmiManager) and keep the JSON export for downstream AI agents.
