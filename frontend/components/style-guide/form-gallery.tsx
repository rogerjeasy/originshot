import { Input, Select, Textarea } from "@/components/ui/input";
import { Field } from "@/components/ui/label";

/**
 * Form controls and their states. `Field` wires up the label, `aria-describedby`
 * and `aria-invalid` — reach for it rather than hand-assembling a label and a
 * control, which is how inputs end up unlabelled.
 */
export function FormGallery() {
  return (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
      <Field htmlFor="sg-default" label="Text input" hint="With helper text">
        <Input placeholder="e.g. Handmade ceramic mug" />
      </Field>

      <Field
        htmlFor="sg-error"
        label="Invalid input"
        error="Enter a product title before generating."
      >
        <Input defaultValue="" placeholder="Required" />
      </Field>

      <Field htmlFor="sg-disabled" label="Disabled">
        <Input placeholder="Not editable" disabled />
      </Field>

      <Field htmlFor="sg-select" label="Select" hint="Native control, themed">
        <Select defaultValue="amazon">
          <option value="amazon">Amazon</option>
          <option value="etsy">Etsy</option>
          <option value="shopify">Shopify</option>
        </Select>
      </Field>

      <Field
        htmlFor="sg-textarea"
        label="Textarea"
        hint="0 of 500 characters"
        className="sm:col-span-2"
      >
        <Textarea rows={4} placeholder="Anything else the studio should know." />
      </Field>
    </div>
  );
}
