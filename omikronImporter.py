bl_info = {
    "name": "Import Omikron models",
    "author": "Chev",
    "version": (0,1),
    "blender": (2, 93, 1),
    "location": "File > Export > Omikron model (*.3DO)",
    "description": 'Import models from "Omikron: the Nomad Soul"',
    "warning": "",
    "wiki_url": "https://github.com/Chevluh/Omikron_Blender_Importer",
    "category": "Import-Export"
}

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from mathutils import *
import re #regex
import time
import os # for path stuff
import ntpath
import math 

from bpy.props import CollectionProperty #for multiple files
from bpy.types import OperatorFileListElement

try: 
    import struct
except: 
    struct = None

###
# https://docs.python.org/3/library/struct.html

def readInt32(file_object):
    return struct.unpack("<i", file_object.read(4))[0] # < little endian, i integer. B would be unsigned char (ie ubyte in c#), ? would be C99 1-byte bool

def readUInt32(file_object):
    return struct.unpack("<I", file_object.read(4))[0]

def readUByte(file_object):
    return struct.unpack("<B", file_object.read(1))[0]

def readFloat(file_object):
    return struct.unpack("<f", file_object.read(4))[0]
    
def readUInt16(file_object):
    return struct.unpack("<H", file_object.read(2))[0]

def readBool(file_object):
    return struct.unpack("<?", file_object.read(1))[0]

def readUInt64(file_object):
    return struct.unpack("<Q", file_object.read(8))[0]

def readUBytes(file_object, count):
    xs = bytearray()       #b'\x01\x02\x03')
    for i in range(count):
        xs.append(readUByte(file_object))
    return xs

def readString(file_object, length = 20):
    return readUBytes(file_object, length).decode("cp858").rstrip('\x00')

def readVector3(file_object):
    x = readFloat(file_object)
    z = -readFloat(file_object)
    y = readFloat(file_object)
    return Vector([x,y,z])

def readColor32(file_object):
    B= readUByte(file_object)/255
    G= readUByte(file_object)/255
    R= readUByte(file_object)/255
    A= readUByte(file_object)/255
    return [R,G,B,A]

###

scalefactor = 0.025 #1/40

#mesh flags
doNotDisplay_jointOnly = 1
vertexLit = 1 << 2
hasParent = 1 << 4
hasChildren = 1 << 5

alphaTesting = 1 << 11

alphablending = 1 << 12
additive = 1 << 13
substractive = 1 << 14

mirror = 1 << 20
FPSarm = 1 << 21
faceMorph = 1 << 22
invisible = 1 << 23

skybox = 1 << 24
environmentMapped = 1 << 26
underwater = 1 << 27
WaterSurface= 1 << 29
WaterUnknown= 1 << 30

###
def readHeader(file_object):
    header = dict()

    header["signature"] = readString(file_object, 4)
    header["versionMajor"] = readUInt32(file_object)
    header["versionMinor"] = readUInt32(file_object)
    header["materialsOffset"] = readUInt32(file_object)
    header["verticesOffset"] = readUInt32(file_object)
    header["trianglesOffset"] = readUInt32(file_object)
    header["rectanglesOffset"] = readUInt32(file_object)
    header["meshesOffset"] = readUInt32(file_object)
    header["doorsOffset"] = readUInt32(file_object)
    header["camerasOffset"] = readUInt32(file_object)
    header["lightsOffset"] = readUInt32(file_object)
    header["reserved"] = readUBytes(file_object, 180)
    header["unknown1"] = readUInt32(file_object)
    header["unknown2"] = readUInt32(file_object)
    header["triangleCount"] = readUInt32(file_object)
    header["rectangleCount"] = readUInt32(file_object)
    header["vertexCount"] = readUInt32(file_object)
    header["reserved2"] = readUInt64(file_object)
    header["materialCount"] = readUInt32(file_object)
    header["unknown3"] = readUInt32(file_object)
    header["reserved3"] = readUInt32(file_object)
    header["cameraCount"] = readUInt32(file_object)
    header["meshCount"] = readUInt32(file_object)
    header["doorCount"] = readUInt32(file_object)
    header["lightCount"] = readUInt32(file_object) #equals lightsunknown1 + lightunknown2
    header["lightsUnknown1"] = readUInt32(file_object) #0 in abetsy, 3 in character
    header["lightsUnknown2"] = readUInt32(file_object) #3 in abetsy, 0 in character
    header["unknown4"] = readUBytes(file_object, 84)

    return header

def readMaterial(file_object):
    material = dict()
    material["name"] = readString(file_object)
    material["BMPfile"] = readString(file_object)
    material["TGAfile"] = readString(file_object)
    material["dataSize"] = readUInt32(file_object)
    material["reserved"] = readUInt64(file_object)
    material["BPP"] = readUInt32(file_object)
    material["width"] = readUInt16(file_object)
    material["height"] = readUInt16(file_object)
    return material

def readMeshDescriptor(file_object):
    meshDescriptor = dict()
    
    meshDescriptor["flags"] = readUInt32(file_object)
    meshDescriptor["moverFlags"] = readUInt32(file_object)
    meshDescriptor["meshID"] = readUInt32(file_object)
    meshDescriptor["scriptID"] = readUInt32(file_object)
    meshDescriptor["name"] = readString(file_object)
    meshDescriptor["position"] = readVector3(file_object) * scalefactor
    meshDescriptor["parentID"] = readInt32(file_object)
    meshDescriptor["firstChildID"] = readInt32(file_object)
    meshDescriptor["nextSiblingID"] = readInt32(file_object)
    meshDescriptor["unknown07_count1"] = readUInt32(file_object)
    meshDescriptor["vertexCount"] = readUInt32(file_object)
    meshDescriptor["triangleCount"] = readUInt32(file_object)
    meshDescriptor["rectangleCount"] = readUInt32(file_object)
    meshDescriptor["unknown08"] = readFloat(file_object)
    meshDescriptor["unknown09"] = readFloat(file_object)
    meshDescriptor["unknown10"] = readFloat(file_object)
    meshDescriptor["unknown11"] = readFloat(file_object)
    meshDescriptor["boxExtentNeg"] = readVector3(file_object) * scalefactor
    meshDescriptor["boxExtentPos"] = readVector3(file_object) * scalefactor
    meshDescriptor["unknown18"] = readFloat(file_object)
    meshDescriptor["unknown19"] = readFloat(file_object)
    meshDescriptor["unknown20"] = readFloat(file_object)
    meshDescriptor["bonePosition"] = readVector3(file_object) * scalefactor

    return meshDescriptor

def readLight(file_object):
    light = dict()
    light["flags"] = readUInt32(file_object)
    light["name"] = readString(file_object)
    light["position"] = [readFloat(file_object), readFloat(file_object), readFloat(file_object)]
    light["angles"] = [readFloat(file_object), readFloat(file_object)]
    light["color"]= [readUByte(file_object)/255,readUByte(file_object)/255,readUByte(file_object)/255,readUByte(file_object)/255]
    light["unknown"] = readUBytes(file_object, 192+64)# [192 octets] Light Points (6 x (12 bytes for pos[x,y,z] + 20 unkown bytes))
    return light

def loadRawVertices(file_object, header, meshDescriptors):
    file_object.seek(header["verticesOffset"])

    fullVertexCount = 0
    for meshDescriptor in meshDescriptors:
        fullVertexCount += meshDescriptor["vertexCount"]

    rawVertices = []
    for i in range(fullVertexCount):
        vertex = dict()
        vertex["bone"] = 0
        for j in range(1, len(meshDescriptors)):
            if i >= meshDescriptors[j]["verticesOffset"]:
                vertex["bone"]+=1
        vertex["position"] = readVector3(file_object) * scalefactor
        vertex["normal"] = readVector3(file_object)
        vertex["t1"] = readUInt32(file_object)
        vertex["color_ARGB"] = readColor32(file_object)
        rawVertices.append(vertex)
    return rawVertices

def GenerateParentTable(meshes):
    IDtoDescriptorIndex = dict()
    for i in range(len(meshes)):
        IDtoDescriptorIndex[meshes[i]["meshID"]] = i;

    results = [];
    for i in range(len(meshes)):
        if meshes[i]["parentID"] == -1:
            result = -1;
        else:
            result = IDtoDescriptorIndex[meshes[i]["parentID"]];
        results.append(result)
    return results


def GenerateSkinTable(meshes):
    IDtoDescriptorIndex = dict()
    for i in range(len(meshes)):
        IDtoDescriptorIndex[meshes[i]["meshID"]] = i;

    results = []
    for i in range(len(meshes)):
        if meshes[i]["parentID"] == -1:
            result = -1;
        else:
            parentCandidate = IDtoDescriptorIndex[meshes[i]["parentID"]];
            while parentCandidate != -1 and meshes[parentCandidate]["flags"] & doNotDisplay_jointOnly != 0:
                parentCandidate = IDtoDescriptorIndex[meshes[parentCandidate]["parentID"]];
            result = parentCandidate;
        results.append(result)
    return results;

def ReadRectangles(rectangleCount, file_object):
    rectangles = []
    for i in range(rectangleCount):
        rectangle = dict()
        rectangle["vertex1"] = readUInt16(file_object)
        rectangle["vertex2"] = readUInt16(file_object)
        rectangle["vertex3"] = readUInt16(file_object)
        rectangle["vertex4"] = readUInt16(file_object)
        rectangle["u1"] = readUByte(file_object)
        rectangle["v1"] = readUByte(file_object)
        rectangle["u2"] = readUByte(file_object)
        rectangle["v2"] = readUByte(file_object)
        rectangle["u3"] = readUByte(file_object)
        rectangle["v3"] = readUByte(file_object)
        rectangle["u4"] = readUByte(file_object)
        rectangle["v4"] = readUByte(file_object)
        rectangle["material"] = readInt32(file_object)
        rectangle["s2"] = readInt32(file_object)
        rectangle["s3"] = readInt32(file_object)
        rectangle["s4"] = readInt32(file_object)

        rectangles.append(rectangle)    
    return rectangles;

def ReadTriangles(triangleCount, file_object):
    triangles = []
    for i in range(triangleCount):
        triangle = dict()
        triangle["vertex1"] = readUInt16(file_object)
        triangle["vertex2"] = readUInt16(file_object)
        triangle["vertex3"] = readUInt16(file_object)
        triangle["u1"] = readUByte(file_object)
        triangle["v1"] = readUByte(file_object)
        triangle["u2"] = readUByte(file_object)
        triangle["v2"] = readUByte(file_object)
        triangle["u3"] = readUByte(file_object)
        triangle["v3"] = readUByte(file_object)
        triangle["material"] = readInt32(file_object)
        triangle["s2"] = readInt32(file_object)
        triangle["s3"] = readInt32(file_object)
        triangle["s4"] = readInt32(file_object)

        triangle["vertex1parented"] = triangle["vertex1"] >> 15 == 1
        triangle["vertex2parented"] = triangle["vertex2"]  >> 15 == 1
        triangle["vertex3parented"] = triangle["vertex3"] >> 15 == 1
        triangle["vertex1"] = triangle["vertex1"] & 1023
        triangle["vertex2"] = triangle["vertex2"] & 1023
        triangle["vertex3"] = triangle["vertex3"] & 1023

        triangles.append(triangle)
    return triangles;

def LoadMeshPolygons(header, meshDescriptor, file_object):
    meshData = dict();
    if meshDescriptor["rectangleCount"] > 0:
        file_object.seek(header["rectanglesOffset"] + meshDescriptor["rectanglesOffset"]);
        meshData["rectangles"] = ReadRectangles(meshDescriptor["rectangleCount"], file_object);
    else:
        meshData["rectangles"] = []

    if meshDescriptor["triangleCount"] > 0:
        file_object.seek(header["trianglesOffset"] + meshDescriptor["trianglesOffset"]);
        meshData["triangles"] = ReadTriangles(meshDescriptor["triangleCount"], file_object);
    else:
        meshData["triangles"] = []
    meshData["descriptor"] = meshDescriptor;
    return meshData;

def DetermineSkin(modelData):
    for meshdata in modelData["meshes"]:
        if meshdata["triangles"] is not None:
            for triangle in meshdata["triangles"]:
                if triangle["vertex1parented"] == True or triangle["vertex2parented"] == True or triangle["vertex3parented"] == True:
                    modelData["isSkinned"] = True
                    return
    modelData["isSkinned"] = False;

def BuildVertices(meshDescriptors, rawVertices, meshCenter):
    vertices = []
    for meshDescriptor in meshDescriptors:
        for i in range(meshDescriptor["vertexCount"]):
            vertex = rawVertices[meshDescriptor["verticesOffset"]+i]
            vertices.append(vertex["position"] + meshDescriptor["position"] - Vector(meshCenter))
    return vertices

def buildFaces(meshDescriptor, triangles, rectangles, parentDescriptor):
    faces =[]
    if len(triangles) > 0:
        for triangle in triangles:
            if triangle["vertex1parented"] == True:
                index1 = parentDescriptor["verticesOffset"] + triangle["vertex1"]
            else:
                index1 = meshDescriptor["verticesOffset"] + triangle["vertex1"]
            if triangle["vertex2parented"] == True:
                index2 = parentDescriptor["verticesOffset"] + triangle["vertex2"]
            else:
                index2 = meshDescriptor["verticesOffset"] + triangle["vertex2"]
            if triangle["vertex3parented"] == True:
                index3 = parentDescriptor["verticesOffset"] + triangle["vertex3"]
            else:
                index3 = meshDescriptor["verticesOffset"] + triangle["vertex3"]
            faces.append([index1, index2, index3])
    if len(rectangles) > 0:
        for rectangle in rectangles:
            index1 = meshDescriptor["verticesOffset"] + rectangle["vertex1"]
            index2 = meshDescriptor["verticesOffset"] + rectangle["vertex2"]
            index3 = meshDescriptor["verticesOffset"] + rectangle["vertex3"]
            index4 = meshDescriptor["verticesOffset"] + rectangle["vertex4"]
            faces.append([index1, index2, index3, index4])
    return faces

def buildUVs(meshDescriptor, triangles, rectangles, textures):
    UVs =[]
    if len(triangles) > 0:
        for triangle in triangles:
            width = textures[triangle["material"]]["width"]
            height = textures[triangle["material"]]["height"]
            uv1 = (triangle["u1"]/width, triangle["v1"]/height)
            uv2 = (triangle["u2"]/width, triangle["v2"]/height)
            uv3 = (triangle["u3"]/width, triangle["v3"]/height)
            UVs.extend([uv1, uv2, uv3])
    if len(rectangles) > 0:
        for rectangle in rectangles:
            width = textures[rectangle["material"]]["width"]
            height = textures[rectangle["material"]]["height"]
            uv1 = (rectangle["u1"]/width, rectangle["v1"]/height)
            uv2 = (rectangle["u2"]/width, rectangle["v2"]/height)
            uv3 = (rectangle["u3"]/width, rectangle["v3"]/height)
            uv4 = (rectangle["u4"]/width, rectangle["v4"]/height)
            UVs.extend([uv1, uv2, uv3, uv4])
    return UVs

def buildVColors(vertices, faces):
    #for each face
    #color is color of referenced vertex
    colors =[]
    for face in faces:
        faceColors = []
        for index in face:
            faceColors.append(vertices[index]["color_ARGB"])
        colors.extend(faceColors)

    return colors

def buildNormals(vertices, faces):
    #same as colors
    normals =[]
    for face in faces:
        faceNormals = []
        for index in face:
            faceNormals.append(vertices[index]["normal"])
        normals.extend(faceNormals)

    return normals

def buildMaterials(meshDescriptor, triangles, rectangles, shaders):
    shaderFlags = makeShaderFlags(meshDescriptor["flags"])
    materials =[]
    if len(triangles) > 0:
        for triangle in triangles:      
            materials.append(shaders[(triangle["material"], shaderFlags)])
    if len(rectangles) > 0:
        for rectangle in rectangles:
            materials.append(shaders[(rectangle["material"], shaderFlags)])
    return materials

###
def computeMeshCenter(meshDescriptors):
    minX = maxX = meshDescriptors[0]["position"].x
    minY = maxY = meshDescriptors[0]["position"].y
    minZ = maxZ = meshDescriptors[0]["position"].z
    for meshDescriptor in meshDescriptors:
        minX = min(minX, meshDescriptor["position"].x)
        maxX = max(maxX, meshDescriptor["position"].x)
        minY = min(minY, meshDescriptor["position"].y)
        maxY = max(maxY, meshDescriptor["position"].y)
        minZ = min(minZ, meshDescriptor["position"].z)
        maxZ = max(maxZ, meshDescriptor["position"].z)
    return ((minX+maxX)/2,(minY+maxY)/2,(minZ+maxZ)/2)

def makeShaderFlags(meshFlags):
    # underwater
    # WaterSurface
    shaderFlags = 0
    if meshFlags & mirror != 0:
        shaderFlags += mirror
        if meshFlags & additive != 0:
            shaderFlags += additive
        if meshFlags & substractive != 0:
            shaderFlags += substractive
    elif meshFlags & environmentMapped != 0:
        shaderFlags += environmentMapped
    elif meshFlags & alphablending != 0:
        shaderFlags += alphablending
        if meshFlags & additive != 0:
            shaderFlags += additive
        if meshFlags & substractive != 0:
            shaderFlags += substractive
    elif meshFlags & alphaTesting != 0:
        shaderFlags += alphaTesting
    if meshFlags & vertexLit != 0:
        shaderFlags += vertexLit
    
    return shaderFlags

def enumerateMaterials(meshes):
    slots = dict() 
    for mesh in meshes:
        if mesh["descriptor"]["flags"] & invisible == 0 and mesh["descriptor"]["flags"] & doNotDisplay_jointOnly == 0:
            shaderFlags = makeShaderFlags(mesh["descriptor"]["flags"])

            for triangle in mesh["triangles"]:
                if not (triangle["material"], shaderFlags) in slots:
                    slots[(triangle["material"], shaderFlags)]=len(slots)
            for rectangle in mesh["rectangles"]:
                if not (rectangle["material"], shaderFlags) in slots:
                    slots[(rectangle["material"], shaderFlags)]=len(slots)
    return slots

def computeMirrorNormal(meshDescriptor, vertices, triangles, rectangles):
    normal = [1,0,0]
    if len(triangles) > 0:
        vertex1 =triangles[0]["vertex1"] + meshDescriptor["verticesOffset"]
        vertex2 =triangles[0]["vertex2"] + meshDescriptor["verticesOffset"]
        vertex3 =triangles[0]["vertex3"] + meshDescriptor["verticesOffset"]    
    elif len(rectangles) > 0:
        vertex1 =rectangles[0]["vertex1"] + meshDescriptor["verticesOffset"]
        vertex2 =rectangles[0]["vertex2"] + meshDescriptor["verticesOffset"]
        vertex3 =rectangles[0]["vertex3"] + meshDescriptor["verticesOffset"]
    v1 = Vector(vertices[vertex2]) - Vector(vertices[vertex1])
    v2 = Vector(vertices[vertex3]) - Vector(vertices[vertex1])
    normal = v1.cross(v2).normalized()
    return Vector(normal)
###

RECTANGLE_SIZE = 32;
TRIANGLE_SIZE = 28;
VERTEX_SIZE = 32;

def ImportModels(file_object, objectName):
    header = readHeader(file_object)
    #print(header)

    file_object.seek(header["materialsOffset"])
    materials = []
    for i in range(header["materialCount"]):
        materials.append(readMaterial(file_object))

    for material in materials:
        print(material)
    
    file_object.seek(header["meshesOffset"])
    meshDescriptors = []

    #while reading mesh descriptors we'll buid absolute offsets to their data
    trianglesOffset = 0; #in bytes
    rectanglesOffset = 0; #in bytes
    verticesOffset = 0; # in vertices

    for i in range(header["meshCount"]):
        meshDescriptor = readMeshDescriptor(file_object)
        meshDescriptors.append(meshDescriptor)
        meshDescriptor["trianglesOffset"] = trianglesOffset
        meshDescriptor["verticesOffset"] = verticesOffset
        meshDescriptor["rectanglesOffset"] = rectanglesOffset
        rectanglesOffset += meshDescriptor["rectangleCount"] * RECTANGLE_SIZE
        trianglesOffset += meshDescriptor["triangleCount"] * TRIANGLE_SIZE
        verticesOffset += meshDescriptor["vertexCount"]
        #print(meshDescriptor)
    
    rawVertices = loadRawVertices(file_object, header, meshDescriptors)

    modelData = dict()
    modelData["parents_hierarchy"] = GenerateParentTable(meshDescriptors)
    modelData["parents_skin"] = GenerateSkinTable(meshDescriptors)

    meshes = []
    for i in range(header["meshCount"]):
        if meshDescriptors[i]["flags"] & invisible == 0:
            meshes.append(LoadMeshPolygons(header, meshDescriptors[i], file_object))
    modelData["meshes"] = meshes

    # lights = []
    # print("light count: {0}".format(header["lightCount"]))
    # print("lightsUnknown1 count: {0}".format(header["lightsUnknown1"]))
    # print("lightsUnknown2 count: {0}".format(header["lightsUnknown2"]))
    # if header["lightsUnknown2"] > 0:
    #     file_object.seek(header["lightsOffset"])
    #     for i in range(header["lightsUnknown2"]):
    #         lights.append(readLight(file_object))
    #         print(lights[i])

    #process the loaded data
    DetermineSkin(modelData)

    #not all meshes are correctly tagged to use baked vertex lighting, good approximation is that if at least one mesh in a file is, all should be
    useLightMaps = False
    for meshDescriptor in meshDescriptors:
        if meshDescriptor["flags"] & vertexLit !=0:
            useLightMaps = True
            break
    if objectName == "VIR_FN": #special fix for virtual fighter, to make it fully bright
        useLightMaps = True
    if useLightMaps:
        for meshDescriptor in meshDescriptors:
            meshDescriptor["flags"] = meshDescriptor["flags"] | vertexLit
    shaders = enumerateMaterials(meshes)

    meshCenter = computeMeshCenter(meshDescriptors)
    vertices = BuildVertices(meshDescriptors, rawVertices, meshCenter)
    faces = []
    UVs = []
    materialIDs = []

    print("model is skinned: {0}".format(modelData["isSkinned"]))
    for i in range(len(modelData["meshes"])):
        meshParent = None;
        if modelData["isSkinned"] and modelData["parents_skin"][i] != -1:
            meshParent = meshDescriptors[modelData["parents_skin"][i]]
        if modelData["meshes"][i]["descriptor"]["flags"] & invisible == 0 and modelData["meshes"][i]["descriptor"]["flags"] & doNotDisplay_jointOnly == 0:
            faces.extend(buildFaces(modelData["meshes"][i]["descriptor"], modelData["meshes"][i]["triangles"], modelData["meshes"][i]["rectangles"], meshParent))
            UVs.extend(buildUVs(modelData["meshes"][i]["descriptor"], modelData["meshes"][i]["triangles"], modelData["meshes"][i]["rectangles"], materials))
            materialIDs.extend(buildMaterials(modelData["meshes"][i]["descriptor"], modelData["meshes"][i]["triangles"], modelData["meshes"][i]["rectangles"], shaders))

    #build the blender mesh
    mesh = bpy.data.meshes.new(objectName)
    mesh.from_pydata(vertices, [], faces)

    new_uv = mesh.uv_layers.new(name = 'DefaultUV')
    for loop in mesh.loops:
        new_uv.data[loop.index].uv = UVs[loop.index]

    colors = buildVColors(rawVertices, faces)
    new_colors = mesh.vertex_colors.new(name = 'DefaultColors')
    for loop in mesh.loops:
        new_colors.data[loop.index].color = colors[loop.index]

    normals = buildNormals(rawVertices, faces)
    mesh.use_auto_smooth = True #needed for custom normals
    mesh.normals_split_custom_set(normals)

    for faceIndex, face in enumerate(mesh.polygons):
        face.material_index = materialIDs[faceIndex]

    mesh.validate() #prevents crash on editing levels for now

    object = bpy.data.objects.new(objectName, mesh)
    object.location = meshCenter
    scene = bpy.context.scene
    scene.collection.objects.link(object)

    #reflection probes
    for i, meshDescriptor in enumerate (meshDescriptors):
        if meshDescriptor["flags"] & environmentMapped !=0:
            probe = bpy.data.lightprobes.new(meshDescriptor["name"]+"_probe", 'CUBE')
            probe.clip_end = 200.0
            probe.influence_distance = meshDescriptor["boxExtentPos"].length + probe.falloff
            probeObject = bpy.data.objects.new(meshDescriptor["name"]+"_probe", probe)
            bpy.context.scene.collection.objects.link(probeObject)
            probeObject.parent = object
            probeObject.location = meshDescriptor["position"] -object.location
        if meshDescriptor["flags"] & mirror !=0:
            probe = bpy.data.lightprobes.new(meshDescriptor["name"]+"_probe", 'PLANAR')
            probe.clip_end = 200.0
            probeObject = bpy.data.objects.new(meshDescriptor["name"]+"_probe", probe)
            bpy.context.scene.collection.objects.link(probeObject)
            probeObject.parent = object
            probeObject.location = meshDescriptor["position"] -object.location
            #change size and orientation to match vertices
            direction = computeMirrorNormal(meshDescriptor, vertices, modelData["meshes"][i]["triangles"], modelData["meshes"][i]["rectangles"])
            rotation = direction.to_track_quat('Z', 'Y').to_euler() #assuming the mirror is pointing up originally
            probeObject.rotation_euler = rotation
            scale = meshDescriptor["boxExtentPos"].length
            probeObject.scale = [scale, scale, 1]

    #skeleton
    if modelData["isSkinned"] == True:
        #adds empty skeleton
        armature = bpy.data.armatures.new(objectName+"_armature")
        armatureObject = bpy.data.objects.new(objectName+"_armature", armature)
        scene.collection.objects.link(armatureObject)
        
        armatureObject.show_in_front = True
        armatureObject.display_type ='WIRE'
        
        #move to edit mode
        bpy.context.window.view_layer.objects.active = armatureObject
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        edit_bones = armatureObject.data.edit_bones
        #for each object, create a bone
        for i, meshDescriptor in enumerate (meshDescriptors):
            bone = edit_bones.new(meshDescriptor["name"])
            bone.head = meshDescriptor["position"] -object.location
            bone.tail = bone.head + Vector([0,0,0.1])
        #link bones into a hierarchy
        for i, meshDescriptor in enumerate (meshDescriptors):
            if modelData["parents_skin"][i] != -1:
                bone = edit_bones[meshDescriptor["name"]]
                bone.parent = edit_bones[meshDescriptors[modelData["parents_skin"][i]]["name"]]
        #orient and connect what we can
        for bone in edit_bones:
            if len(bone.children) == 1:
                bone.tail = bone.children[0].head
                bone.children[0].use_connect = True
            elif len(bone.children) == 0 and bone.parent is not None:
                bone.tail = bone.head + (bone.head - bone.parent.head) /2
        bpy.ops.object.mode_set(mode = 'OBJECT')

        #for each mesh that is not joint-only, create a vertex group
        for meshDescriptor in meshDescriptors:
            if meshDescriptor["flags"] & doNotDisplay_jointOnly == 0:
                vertexGroup = object.vertex_groups.new(name=meshDescriptor["name"])
                vertexGroup.add(range(meshDescriptor["verticesOffset"], meshDescriptor["verticesOffset"]+ meshDescriptor["vertexCount"]), 1.0, 'ADD')
        
        #parent mesh to armature
        armatureObject.location = object.location
        object.parent = armatureObject
        object.location = [0,0,0]
        modifier = object.modifiers.new("Armature", 'ARMATURE')
        modifier.object = armatureObject
        
    # #lights
    # for lightDescriptor in lights:
    #     lightObject = bpy.data.objects.new( lightDescriptor["name"], None )
    #     scene.collection.objects.link(lightObject)
    #     lightObject.empty_display_size = 2
    #     lightObject.empty_display_type = 'PLAIN_AXES'
    #     lightObject.parent = object
    #     lightObject.location = (lightDescriptor["position"][0] * scalefactor -object.location[0], lightDescriptor["position"][2] * scalefactor -object.location[1], -lightDescriptor["position"][1] * scalefactor -object.location[2])
        

    return mesh, materials, shaders;

def ReadPalette(file_object, colorCount):
    palette = []
    for i in range(colorCount):
        red = readUByte(file_object)
        green = readUByte(file_object)
        blue = readUByte(file_object)
        alpha = 0 if (red == 0 and green == 0 and blue == 0) else 1
        palette.append([red/255, green/255, blue/255, alpha])
    return palette

def Decompress(file_object, compressedSize, uncompressedSize):
    startAddress = file_object.tell()
    if compressedSize == 65536:
        return readUBytes(file_object, compressedSize)
    result = []
    result.append(readUByte(file_object)) # first byte isn't compressed
    currentByte = 1
    while currentByte < uncompressedSize:
        flags = readUByte(file_object)
        for flagIndex in range(8):
            CompressionFlag = (flags >> (7 - flagIndex) & 1) != 0
            if CompressionFlag == True:
                sequenceDescription = readUByte(file_object)
                sequenceType = sequenceDescription & 3
                sequenceSize = (sequenceDescription >> 2) + 3
                offset = 0
                if sequenceType == 0:
                    # répétition du pixel précédent 
                    # (pixel précédent inclus dans la taille de la séquence) 
                    offset = 1;
                    sequenceSize -= 1

                elif sequenceType == 1:
                    # copie d'une séquence de pixels,
                    # (n) pixels avant le pixel précédent (prochain octet = valeur de n)
                    offset = 1 + readUByte(file_object)

                elif sequenceType == 2:
                    # copie d'une séquence de pixels,
                    # (n) pixels avant le pixel précédent (2 prochains octets = valeur de n)
                    offset = 1 + (readUByte(file_object) << 8) + readUByte(file_object)

                elif sequenceType == 3:
                    # copie d'une séquence de pixels, (n) pixels avant le pixel précédent
                    # (n = (256 * prochain octet) -1)
                    offset = 1 + readUByte(file_object) * 256 - 1
                else:
                    raise Exception("invalid flag")

                for i in range(sequenceSize):
                    if offset > currentByte:
                        result.append(0)
                    else:
                        result.append(result[currentByte - offset])
                    currentByte += 1
                    if currentByte >= uncompressedSize:
                        return result
            else:
                result.append(readUByte(file_object))
                currentByte += 1
                if (currentByte >= uncompressedSize):
                    return result

            currentAddress = file_object.tell()
            if currentAddress - startAddress >= compressedSize:
                return result
    return result

def ApplyPalette(palette, texture):
    result = []
    for pixel in range(len(texture)):
        result.extend(palette[texture[pixel]])
    return result

def ImportTextures(file_object, mesh, materials, shaders):
    offset = 0
    images = []

    slots = []
    keys = list(shaders.keys())
    values = list(shaders.values())
    for i in range(len(shaders)):
        slots.append(keys[values[i]])

    for material in materials:
        file_object.seek(offset)
        colorCount = 2**material["BPP"]
        palette = ReadPalette(file_object, colorCount)
        indexTexture = Decompress(file_object, material["dataSize"], material["width"] * material["height"])
        imageData = ApplyPalette(palette, indexTexture)

        image = bpy.data.images.new(material["name"], material["width"], material["height"], alpha = True)
        image.pixels = imageData
        image.file_format = 'PNG'
        image.pack()

        images.append(image)
        offset += material["dataSize"] + colorCount * 3;

    for slot in slots:
        material = materials[slot[0]]
        shaderflags = slot[1]

        mat = bpy.data.materials.new(material["name"])
        mat.use_nodes = True
        mat.use_backface_culling = True
        nodes = mat.node_tree.nodes
        nodes.remove(nodes["Principled BSDF"])
        textureNode=nodes.new("ShaderNodeTexImage")
        textureNode.image = images[slot[0]]

        if mesh.name == "shadows":
            #material cheat for shadow
            transparentNode =nodes.new("ShaderNodeBsdfTransparent")
            mixNode =nodes.new("ShaderNodeMixShader")
            mat.node_tree.links.new(mixNode.inputs[0], textureNode.outputs[0]) #texture color as factor
            mat.node_tree.links.new(mixNode.inputs[1], transparentNode.outputs[0])
            mat.node_tree.links.new(nodes['Material Output'].inputs[0], mixNode.outputs[0])
            mat.blend_method = 'BLEND'
            mat.shadow_method = 'NONE'    
        else:
            #first decide between using vertex lighting or diffuse shader
            if shaderflags & vertexLit != 0:
                vColorNode = nodes.new("ShaderNodeVertexColor")
                vColorNode.layer_name = 'DefaultColors'
                diffuseNode = nodes.new("ShaderNodeMixRGB")
                diffuseNode.blend_type = 'MULTIPLY'

                diffuseNode.inputs[0].default_value = 0.9 #0.7 #blend factor
                mat.node_tree.links.new(diffuseNode.inputs[2], vColorNode.outputs[0])
                mat.node_tree.links.new(diffuseNode.inputs[1], textureNode.outputs[0])
            else:
                diffuseNode = nodes.new('ShaderNodeBsdfDiffuse')
                mat.node_tree.links.new(diffuseNode.inputs[0], textureNode.outputs[0])

            #then decide on possibility of alpha or reflections
            if shaderflags & alphablending != 0:
                transparentNode =nodes.new("ShaderNodeBsdfTransparent")
                addNode =nodes.new("ShaderNodeAddShader")
                mat.node_tree.links.new(addNode.inputs[0], transparentNode.outputs[0])
                mat.node_tree.links.new(addNode.inputs[1], diffuseNode.outputs[0])
                mat.node_tree.links.new(nodes['Material Output'].inputs[0], addNode.outputs[0])
                mat.blend_method = 'BLEND'
                mat.shadow_method = 'NONE'
            elif shaderflags & alphaTesting != 0:
                transparentNode =nodes.new("ShaderNodeBsdfTransparent")
                mixNode =nodes.new("ShaderNodeMixShader")
                mat.node_tree.links.new(mixNode.inputs[0], textureNode.outputs[1]) #texture alpha as factor
                mat.node_tree.links.new(mixNode.inputs[1], transparentNode.outputs[0])
                mat.node_tree.links.new(mixNode.inputs[2], diffuseNode.outputs[0])
                mat.node_tree.links.new(nodes['Material Output'].inputs[0], mixNode.outputs[0])
                mat.blend_method = 'CLIP'
                mat.alpha_threshold = 0.999
                mat.shadow_method = 'CLIP'
            elif shaderflags & mirror != 0:
                glossNode = nodes.new("ShaderNodeBsdfGlossy")
                glossNode.inputs["Roughness"].default_value = 0
                #mixNode =nodes.new("ShaderNodeMixShader")
                #mixNode.inputs[0].default_value = 0.5
                if shaderflags & substractive != 0:
                    invertNode =nodes.new("ShaderNodeInvert")
                    mat.node_tree.links.new(invertNode.inputs[1], diffuseNode.outputs[0])
                    mat.node_tree.links.new(glossNode.inputs[0], invertNode.outputs[0])
                    mat.node_tree.links.new(nodes['Material Output'].inputs[0], glossNode.outputs[0])
                else:
                    #assuming additive
                    addNode =nodes.new("ShaderNodeAddShader")
                    mat.node_tree.links.new(addNode.inputs[0], glossNode.outputs[0])
                    mat.node_tree.links.new(addNode.inputs[1], diffuseNode.outputs[0])
                    mat.node_tree.links.new(nodes['Material Output'].inputs[0], addNode.outputs[0])
            elif shaderflags & environmentMapped != 0:
                glossNode = nodes.new("ShaderNodeBsdfPrincipled")
                glossNode.inputs["Base Color"].default_value = (0.3,0.3,0.3,0)
                glossNode.inputs["Roughness"].default_value = 0
                glossNode.inputs["Specular"].default_value = 1
                glossNode.inputs["Metallic"].default_value = 1

                mat.node_tree.links.new(glossNode.inputs["Emission"], diffuseNode.outputs[0])
                mat.node_tree.links.new(nodes['Material Output'].inputs[0], glossNode.outputs[0])
                diffuseNode.inputs[0].default_value = 1 #0.9
            else:
                mat.node_tree.links.new(nodes['Material Output'].inputs[0], diffuseNode.outputs[0])

        mesh.materials.append(mat)

###

class ImportOmikron(bpy.types.Operator, ImportHelper):
    bl_idname       = "import_omikron.chev";
    bl_label        = "import 3DO";
    bl_options      = {'PRESET'};
    
    filename_ext    = ".3do";

    filter_glob: StringProperty(
        default="*.3do",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )
    
    # files = CollectionProperty(
    #     name="3DO files",
    #     type=OperatorFileListElement,
    #     )

    # directory = StringProperty(subtype='DIR_PATH')

    def execute(self, context):
        print("importer start")
        then = time.time()
        # for f in self.files:
        #     print(f)
        # print(self.directory)

        modelFilePath = self.filepath
        fileName = modelFilePath[:-3]
        textureFilePath = fileName+"3dt"
        print("modelFilePath: {0}".format(modelFilePath))
        print("textureFilePath: {0}".format(textureFilePath))
        model_in = open(modelFilePath, "rb")
        mesh, materials, shaders = ImportModels(model_in, ntpath.basename(modelFilePath[:-4]))
        model_in.close()
        
        if os.path.exists(textureFilePath):
            textures_in = open(textureFilePath, "rb")
            ImportTextures(textures_in, mesh, materials, shaders)
            textures_in.close()

        now = time.time()
        print("It took: {0} seconds".format(now-then))
        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(ImportOmikron.bl_idname, text="Omikron model (*.3DO)");

def register():
    from bpy.utils import register_class
    register_class(ImportOmikron)
    bpy.types.TOPBAR_MT_file_import.append(menu_func)
    
def unregister():
    from bpy.utils import unregister_class
    unregister_class(ImportOmikron)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func);

if __name__ == "__main__":
    register()