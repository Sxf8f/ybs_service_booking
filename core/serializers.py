from rest_framework import serializers
from .models import CollectionTransfer, Operator, TypeOfService, User, WorkFromTheRole, Material, WorkReport, WorkStb



class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField()

    class Meta:
        model = User
        fields = '__all__'

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.password = password
        user.save()
        return user

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "name", "phone", "alternate_no", "whatsapp_no", "email",
            "address", "pincode", "remark", "password", "role", "undersupervisor"
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.password = password  # plain
        user.save()
        return user




class CollectionTransferSerializer(serializers.ModelSerializer):
    technician_name = serializers.CharField(source="technician.name", read_only=True)
    supervisor_name = serializers.CharField(source="supervisor.name", read_only=True)

    class Meta:
        model = CollectionTransfer
        fields = "__all__"




class OperatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Operator
        fields = '__all__'

class TypeOfServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeOfService
        fields = '__all__'

class WorkFromTheRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkFromTheRole
        fields = '__all__'

class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = '__all__'










class WorkStbSerializer(serializers.ModelSerializer):
    operator_name = serializers.CharField(source='operator.name', read_only=True)
    service_type_name = serializers.CharField(source='service_type.name', read_only=True)
    work_from_name = serializers.CharField(source='work_from.name', read_only=True)
    supervisor_name = serializers.CharField(source='supervisor.name', read_only=True)
    assigned_technician_name = serializers.CharField(source='assigned_technician.name', read_only=True)

    class Meta:
        model = WorkStb
        fields = '__all__'




class WorkReportSerializer(serializers.ModelSerializer):
    work_details = serializers.SerializerMethodField()

    class Meta:
        model = WorkReport
        fields = '__all__'

    def get_work_details(self, obj):
        work = obj.work
        return {
            "id": work.id,
            "customer_name": work.customer_name,
            "operator": work.operator.name if work.operator else None,
            "type_of_service": work.type_of_service.name if work.type_of_service else None,
            "supervisor": work.supervisor.name if work.supervisor else None,
            "assigned_technician": work.assigned_technician.name if work.assigned_technician else None,
            "work_from": work.work_from.name if work.work_from else None,
            "status": work.status,
            "amount": work.amount,
            "work_got_time": work.work_got_time,
        }


