/// A second cube over the same rows, so a query can name a dimension that is not its own.
Class IadLive131.OtherCube Extends %DeepSee.CubeDefinition [ DependsOn = IadLive131.Sale ]
{

XData Cube [ XMLNamespace = "http://www.intersystems.com/deepsee" ]
{
<cube xmlns="http://www.intersystems.com/deepsee" name="IadLive131Other" sourceClass="IadLive131.Sale">
  <dimension name="OtherD" hasAll="true">
    <hierarchy name="H1">
      <level name="Region" sourceProperty="Region"/>
    </hierarchy>
  </dimension>
</cube>
}

}
